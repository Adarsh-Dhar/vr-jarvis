'''
API key pool: use several Gemini API keys and move to the next one when a key runs out.

Keys are read (lazily, so .env is already loaded) from, in this order, without duplicates:
  GOOGLE_API_KEY, GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ... (numeric order), JARVIS_API_KEYS (comma separated)

Behaviour:
  * With 0 or 1 key nothing changes: the Google client reads GOOGLE_API_KEY from the environment as before.
  * With 2+ keys the pool uses the first ready key in the listed order (so GOOGLE_API_KEY is preferred and
    takes over again as soon as it recovers) and moves to the next one when a key fails.
    The last used key is remembered in a small state file, so after a restart the pool resumes
    on that key and keeps using it until it rests or dies; if it is no longer configured the
    pool starts from GOOGLE_API_KEY as usual.
    State file: JARVIS_KEY_STATE_FILE, default ~/.config/jarvis/api_key_pool.json
      - 429 / RESOURCE_EXHAUSTED  -> the key rests (Google's retryDelay, or until the daily reset
                                     for per-day quotas), then comes back.
      - key expired / invalid / permission denied (400, 401, 403) -> the key is dropped until restart.
      - anything else (5xx, network, bad request) -> raised as before; the key is NOT blamed.
  * JARVIS_KEY_STRATEGY=round_robin spreads calls over all keys instead of sticking to one.
  * JARVIS_KEY_MAX_WAIT (seconds, default 20): if every key is resting longer than this, fail fast.
  * Repeated quota failures on the same key back off exponentially (up to JARVIS_KEY_BACKOFF_MAX,
    default 8x Google's suggested wait), so a truly exhausted key is not retried every ~30s.
  * A background prober (JARVIS_KEY_PROBE=0 disables) checks a resting key with a 1-token call a few
    seconds before its rest expires (JARVIS_KEY_PROBE_LEAD, default 4s; tick JARVIS_KEY_PROBE_TICK,
    default 2s). If quota is still gone the rest is extended before any real call touches the key.
    The probe reuses the model and endpoint the key last served, because Gemini quotas are per model.
Keys are never logged in full, only as '...abcd'.

Note: Google free-tier quotas are per Google Cloud project, not per key. Keys created in the same
project share one quota, so rotation only helps with keys from different projects (or billing accounts).
'''
import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta

log = logging.getLogger('uvicorn.error')

_BAD_KEY_TEXT = ('api key expired', 'api_key_invalid', 'api key not valid', 'api key not found',
                 'permission_denied', 'api has not been used', 'consumer_suspended')


def load_keys(env=None):
    env = os.environ if env is None else env
    keys = []

    def add(k):
        k = (k or '').strip().strip('\'"')
        if k and k not in keys:
            keys.append(k)

    add(env.get('GOOGLE_API_KEY'))
    numbered = []
    for name, value in env.items():
        m = re.fullmatch(r'GOOGLE_API_KEY_(\d+)', name)
        if m:
            numbered.append((int(m.group(1)), value))
    for _, value in sorted(numbered):
        add(value)
    for value in (env.get('JARVIS_API_KEYS') or '').split(','):
        add(value)
    return keys


def label(key):
    return '...' + key[-4:] if key else '?'


def _fp(key):
    '''Short fingerprint of a key for the state file; never stores the key itself.'''
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _state_file_path():
    return os.path.expanduser(os.getenv('JARVIS_KEY_STATE_FILE', '~/.config/jarvis/api_key_pool.json'))


def _seconds_until_daily_reset():
    '''Gemini daily quotas reset at midnight Pacific time.'''
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo('America/Los_Angeles'))
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        return max(60.0, (nxt - now).total_seconds())
    except Exception:
        return 6 * 3600.0


def _retry_delay(details):
    '''Pull Google's suggested retry delay (e.g. '34s') out of the error details, if present.'''
    try:
        for d in (details or {}).get('error', {}).get('details', []):
            rd = d.get('retryDelay')
            if rd:
                return float(str(rd).rstrip('s'))
    except Exception:
        pass
    return None


def classify(exc):
    '''Return ('quota', seconds) | ('dead', None) | ('other', None) for a model-call exception.'''
    code = getattr(exc, 'code', None)
    status = str(getattr(exc, 'status', '') or '').upper()
    details = getattr(exc, 'details', None)
    text = (str(getattr(exc, 'message', '') or '') + ' ' + str(details or '') + ' ' + str(exc)).lower()
    if code == 429 or status == 'RESOURCE_EXHAUSTED':
        if 'perday' in text.replace('_', '').replace(' ', '') or 'per day' in text:
            return 'quota', _seconds_until_daily_reset()
        return 'quota', max(5.0, min(_retry_delay(details) or 60.0, 3600.0))
    if code in (400, 401, 403) and any(s in text for s in _BAD_KEY_TEXT):
        return 'dead', None
    return 'other', None


class KeyPool:
    def __init__(self, keys, strategy='sticky', state_path=None):
        self.keys = list(keys)
        self.strategy = strategy
        self._lock = threading.Lock()
        self._until = {k: 0.0 for k in self.keys}      # key -> time it can be used again
        self._dead = {}                                  # key -> reason
        self._why = {}
        self._i = 0
        self._resume = None                               # preferred index restored from the state file; sticky keeps it until unusable
        self._state_path = state_path
        self._persisted = None                           # index last written to the state file
        self._fails = {}                                  # key -> consecutive quota failures (drives backoff)
        self._used = {}                                   # key -> successful calls served (for /metrics/llm)
        self._last_call = {}                              # key -> (model, base_url) last served, for quota probes
        self._probe_thread = None
        self._probe_stop = threading.Event()
        self._restore()

    def _restore(self):
        '''Resume from the last used key on the first pick after startup. If it is no longer
        configured, start at index 0 (GOOGLE_API_KEY) as usual.'''
        if not self._state_path:
            return
        try:
            with open(os.path.expanduser(self._state_path)) as f:
                data = json.load(f)
            fp = data.get('fp')
        except Exception:
            return
        if not fp:
            return
        for idx, k in enumerate(self.keys):
            if _fp(k) == fp:
                self._persisted = idx
                if self.strategy == 'round_robin':
                    self._i = (idx + 1) % len(self.keys)
                else:
                    self._resume = idx
                log.info('resuming API key pool at key %s', label(k))
                return
        log.warning('API key state file %s matches no configured key (stored index %s); '
                    'starting from %s', self._state_path, data.get('index'),
                    label(self.keys[0]) if self.keys else '?')

    def _save(self, idx):
        if not self._state_path or idx == self._persisted:
            return
        try:
            path = os.path.expanduser(self._state_path)
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'index': idx, 'fp': _fp(self.keys[idx]), 'key': label(self.keys[idx])}, f)
            os.replace(tmp, path)
            self._persisted = idx
        except Exception as exc:
            log.debug('could not persist API key state: %s', exc)

    def __len__(self):
        return len(self.keys)

    def note_model(self, key, model, base_url=None):
        '''Remember which model/endpoint a key last served so the prober can check the same quota.'''
        with self._lock:
            self._last_call[key] = (model, base_url)

    def ok(self, key):
        '''A call on this key succeeded: reset its consecutive-failure count.'''
        with self._lock:
            self._fails.pop(key, None)
            self._used[key] = self._used.get(key, 0) + 1

    def _maybe_start_prober(self):
        if os.getenv('JARVIS_KEY_PROBE', '1') == '0':
            return
        if self._probe_thread is None or not self._probe_thread.is_alive():
            self._probe_stop.clear()
            self._probe_thread = threading.Thread(target=self._probe_loop, daemon=True,
                                                  name='api-key-prober')
            self._probe_thread.start()

    def _probe_loop(self):
        tick = float(os.getenv('JARVIS_KEY_PROBE_TICK', '2'))
        lead = float(os.getenv('JARVIS_KEY_PROBE_LEAD', '4'))
        while not self._probe_stop.wait(tick):
            try:
                self._probe_pass(lead)
            except Exception as exc:
                log.debug('API key probe pass failed: %s', exc)

    def _probe_pass(self, lead):
        '''Probe resting keys that are about to become usable again, before a real call finds them dead.'''
        now = time.time()
        with self._lock:
            due = [k for k in self.keys
                   if k not in self._dead and now < self._until.get(k, 0.0) <= now + lead]
        for key in due:
            mc = self._last_call.get(key)
            if not mc or not mc[0]:
                continue
            model, base_url = mc
            try:
                _probe(key, model, base_url)
                log.info('API key %s quota probe OK', label(key))
            except Exception as exc:
                kind, secs = classify(exc)
                if kind == 'quota':
                    # still exhausted: extend the rest before any real call hits this key
                    self.mark(key, 'quota', secs, exc)
                elif kind == 'dead':
                    self.mark(key, 'dead', exc=exc)
                # 'other' errors say nothing about quota; leave the key alone

    def close(self):
        self._probe_stop.set()

    def get(self):
        '''Best usable key right now, or None if all are resting or dead.'''
        with self._lock:
            now = time.time()
            n = len(self.keys)
            rr = self.strategy == 'round_robin'
            if not rr and self._resume is not None:
                # sticky resume: keep using the restored key until it rests or dies
                k = self.keys[self._resume]
                if k not in self._dead and self._until[k] <= now:
                    self._save(self._resume)
                    return k
                self._resume = None
            start = self._i if rr else 0           # sticky: the first ready key, in listed order
            for step in range(n):
                idx = (start + step) % n
                k = self.keys[idx]
                if k not in self._dead and self._until[k] <= now:
                    if rr:
                        self._i = (idx + 1) % n
                    self._save(idx)
                    return k
            return None

    def wait_seconds(self):
        '''Seconds until some key is usable again; None if every key is dead.'''
        with self._lock:
            live = [self._until[k] for k in self.keys if k not in self._dead]
            if not live:
                return None
            return max(0.0, min(live) - time.time())

    def mark(self, key, kind, seconds=None, exc=None):
        with self._lock:
            if kind == 'dead':
                self._dead[key] = str(exc)[:120]
                log.warning('API key %s is invalid or expired; dropped until restart', label(key))
            else:
                # back off exponentially on consecutive quota failures, capped so a per-day
                # rest (already hours long) is never shortened
                self._fails[key] = self._fails.get(key, 0) + 1
                mult = min(2 ** (self._fails[key] - 1),
                           int(os.getenv('JARVIS_KEY_BACKOFF_MAX', '8')))
                base = seconds or 60.0
                rest = max(base, min(base * mult, 3600.0))
                self._until[key] = time.time() + rest
                self._why[key] = 'quota'
                log.warning('API key %s is out of quota; resting %ds, switching key',
                            label(key), int(rest))
                self._maybe_start_prober()

    def status(self):
        now = time.time()
        with self._lock:
            return [{'key': label(k),
                     'state': 'dead' if k in self._dead else ('resting' if self._until[k] > now else 'ready'),
                     'resting_s': max(0, int(self._until[k] - now)),
                     'fails': self._fails.get(k, 0),
                     'calls': self._used.get(k, 0)} for k in self.keys]


_pool = None
_pool_lock = threading.Lock()
_pool_state_path = None


def get_pool():
    global _pool, _pool_state_path
    with _pool_lock:
        if _pool is None:
            _pool_state_path = _state_file_path()
            _pool = KeyPool(load_keys(), os.getenv('JARVIS_KEY_STRATEGY', 'sticky'), _pool_state_path)
        return _pool


def reset():
    '''Forget the pool so the next call re-reads the environment (used by tests).
    Also drops the persisted key position.'''
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        if _pool_state_path:
            try:
                os.remove(os.path.expanduser(_pool_state_path))
            except OSError:
                pass


def _probe(key, model, base_url=None):
    '''One-token generate call used only to learn whether a resting key has quota again.
    Raises the same exceptions a real call would, so classify() can read them.'''
    from google import genai
    from google.genai import types
    kwargs = {'api_key': key}
    if base_url:
        kwargs['http_options'] = types.HttpOptions(base_url=base_url)
    client = genai.Client(**kwargs)
    client.models.generate_content(
        model=model, contents='hi',
        config=types.GenerateContentConfig(max_output_tokens=1))


def with_client(fn):
    '''Run fn(genai_client) once, moving to the next key on quota or key errors.
    With fewer than 2 keys this is just fn(genai.Client()) like before.'''
    from google import genai
    pool = get_pool()
    if len(pool) < 2:
        return fn(genai.Client())
    last = None
    for _ in range(len(pool)):
        key = pool.get()
        if key is None:
            break
        try:
            result = fn(genai.Client(api_key=key))
            pool.ok(key)
            return result
        except Exception as exc:
            kind, secs = classify(exc)
            if kind == 'other':
                raise
            pool.mark(key, kind, secs, exc)
            last = exc
    raise last or RuntimeError('no usable API key')
