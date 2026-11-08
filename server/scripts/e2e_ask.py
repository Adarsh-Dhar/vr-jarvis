#!/usr/bin/env python3
"""
End-to-end test for the JARVIS agent: real HTTP request -> real agent -> real response.

Creates a session, sends a question to /ask (the same endpoint the Unity VR client uses),
and validates the full response contract. No mocks, no shortcuts.

Usage:
    python3 server/scripts/e2e_ask.py ["question text"]

Requires the server running (./server/start.sh) and reads JARVIS_TOKEN / base URL from env
or the repo .env file.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = os.getenv('JARVIS_URL', 'http://127.0.0.1:8000').rstrip('/')
QUESTION = sys.argv[1] if len(sys.argv) > 1 else 'Who caused training in the court?'
TIMEOUT = int(os.getenv('JARVIS_TEST_TIMEOUT', '200'))


def load_env():
    env_file = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, {'http_error': e.read().decode()[:500]}
    except Exception as e:
        return 0, {'error': f'{type(e).__name__}: {e}'}


def main():
    load_env()
    token = os.getenv('JARVIS_TOKEN', '')

    print(f'== health ==')
    code, health = call('GET', '/health')
    print(f'  {code} {health}')
    assert code == 200 and health.get('ok'), 'server not healthy'

    print(f'\n== POST /session ==')
    code, sess = call('POST', '/session', token=token)
    print(f'  {code} {sess}')
    assert code == 200, f'session failed: {sess}'
    session_id = sess['session_id']

    print(f'\n== POST /ask ==')
    print(f'  request: session_id={session_id}')
    print(f'           text={QUESTION!r}')
    t0 = time.time()
    code, resp = call('POST', '/ask', {'session_id': session_id, 'text': QUESTION, 'selection': ''}, token=token)
    elapsed = time.time() - t0
    print(f'  http={code} elapsed={elapsed:.1f}s')
    print(f'  response: {json.dumps(resp, indent=2)[:4000]}')

    assert code == 200, f'/ask http {code}: {resp}'
    assert resp.get('reply'), f'empty reply: {resp}'
    assert not resp.get('error'), f'agent error: {resp.get("error")}'

    # Validate the full contract the Unity client expects
    expected = {'reply', 'error', 'scene_commands', 'pending_approval', 'approved',
                'test_results', 'test_source', 'evidence', 'approval_type'}
    assert set(resp.keys()) == expected, f'contract mismatch: {set(resp.keys()) ^ expected}'
    for cmd in resp.get('scene_commands', []):
        assert cmd.get('type'), f'scene command missing type: {cmd}'

    print(f'\nPASS: agent answered in {elapsed:.1f}s')
    print(f'  reply: {resp["reply"][:300]}')
    if resp.get('scene_commands'):
        print(f'  scene_commands: {[c.get("type") for c in resp["scene_commands"]]}')
    if resp.get('evidence'):
        print(f'  evidence: {len(resp["evidence"])} item(s)')


if __name__ == '__main__':
    main()
