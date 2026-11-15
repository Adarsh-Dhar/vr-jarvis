'''
API key pool: use several Gemini API keys and move to the next one when a key runs out.

Keys are read (lazily, so .env is already loaded) from, in this order, without duplicates:
  GOOGLE_API_KEY, GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ... (numeric order), JARVIS_API_KEYS (comma separated)

Behaviour:
  * With 0 or 1 key nothing changes: the Google client reads GOOGLE_API_KEY from the environment as before.
  * With 2+ keys the pool uses the first ready key in the listed order (so GOOGLE_API_KEY is preferred and
    takes over again as soon as it recovers) and moves to the next one when a key fails.
      - 429 / RESOURCE_EXHAUSTED  -> the key rests (Google's retryDelay, or until the daily reset
                                     for per-day quotas), then comes back.
      - key expired / invalid / permission denied (400, 401, 403) -> the key is dropped until restart.
      - anything else (5xx, network, bad request) -> raised as before; the key is NOT blamed.
  * JARVIS_KEY_STRATEGY=round_robin spreads calls over all keys instead of sticking to one.
  * JARVIS_KEY_MAX_WAIT (seconds, default 20): if every key is resting longer than this, fail fast.
Keys are never logged in full, only as '...abcd'.

Note: Google free-tier quotas are per Google Cloud project, not per key. Keys created in the same
project share one quota, so rotation only helps with keys from different projects (or billing accounts).
'''
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
    def __init__(self, keys, strategy='sticky'):
        self.keys = list(keys)
        self.strategy = strategy
        self._lock = threading.Lock()
        self._until = {k: 0.0 for k in self.keys}      # key -> time it can be used again
        self._dead = {}                                  # key -> reason
        self._why = {}
        self._i = 0

    def __len__(self):
        return len(self.keys)

    def get(self):
        '''Best usable key right now, or None if all are resting or dead.'''
        with self._lock:
            now = time.time()
            n = len(self.keys)
            rr = self.strategy == 'round_robin'
            start = self._i if rr else 0           # sticky: always the first ready key, in listed order
            for step in range(n):
                idx = (start + step) % n
                k = self.keys[idx]
                if k not in self._dead and self._until[k] <= now:
                    if rr:
                        self._i = (idx + 1) % n
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
                self._until[key] = time.time() + (seconds or 60.0)
                self._why[key] = 'quota'
                log.warning('API key %s is out of quota; resting %ds, switching key', label(key), int(seconds or 60))

    def status(self):
        now = time.time()
        with self._lock:
            return [{'key': label(k),
                     'state': 'dead' if k in self._dead else ('resting' if self._until[k] > now else 'ready'),
                     'resting_s': max(0, int(self._until[k] - now))} for k in self.keys]


_pool = None
_pool_lock = threading.Lock()


def get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = KeyPool(load_keys(), os.getenv('JARVIS_KEY_STRATEGY', 'sticky'))
        return _pool


def reset():
    '''Forget the pool so the next call re-reads the environment (used by tests).'''
    global _pool
    with _pool_lock:
        _pool = None


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
            return fn(genai.Client(api_key=key))
        except Exception as exc:
            kind, secs = classify(exc)
            if kind == 'other':
                raise
            pool.mark(key, kind, secs, exc)
            last = exc
    raise last or RuntimeError('no usable API key')
