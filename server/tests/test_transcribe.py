"""Contract tests for POST /transcribe (speech to text for the VR client). The model call is replaced."""
import base64
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import jarvis_server
from jarvis_server import app

# Set a token for testing so auth is enforced
os.environ['JARVIS_TOKEN'] = 'test-token'
jarvis_server.TOKEN = 'test-token'

HEADERS = {'authorization': 'Bearer test-token'}
WAV = base64.b64encode(b'RIFF' + b'\x00' * 4000).decode()


def post(body):
    return TestClient(app).post('/transcribe', json=body, headers=HEADERS)


def test_transcribe_returns_text(monkeypatch):
    seen = {}
    monkeypatch.setattr(jarvis_server, '_transcribe_audio', lambda audio, mime: seen.update(n=len(audio), mime=mime) or 'what breaks if I change train')
    r = post({'audio_base64': WAV, 'mime': 'audio/wav'})
    assert r.status_code == 200
    assert r.json() == {'text': 'what breaks if I change train', 'error': ''}
    assert seen == {'n': 4004, 'mime': 'audio/wav'}


def test_transcribe_requires_token():
    r = TestClient(app).post('/transcribe', json={'audio_base64': WAV})
    assert r.status_code in (401, 403)


def test_transcribe_rejects_bad_input(monkeypatch):
    monkeypatch.setattr(jarvis_server, '_transcribe_audio', lambda audio, mime: 'x')
    assert post({'audio_base64': '!!notbase64!!'}).status_code == 400
    assert post({'audio_base64': WAV, 'mime': 'text/plain'}).status_code == 400
    monkeypatch.setattr(jarvis_server, 'MAX_AUDIO_BYTES', 100)
    assert post({'audio_base64': WAV}).status_code == 413


def test_transcribe_short_audio_is_not_sent_to_the_model(monkeypatch):
    monkeypatch.setattr(jarvis_server, '_transcribe_audio', lambda a, m: (_ for _ in ()).throw(AssertionError('model must not be called')))
    r = post({'audio_base64': base64.b64encode(b'RIFF').decode()})
    assert r.json() == {'text': '', 'error': 'audio too short'}


def test_transcribe_model_failure_becomes_an_error_field(monkeypatch):
    def boom(audio, mime):
        raise RuntimeError('quota exceeded')
    monkeypatch.setattr(jarvis_server, '_transcribe_audio', boom)
    r = post({'audio_base64': WAV})
    assert r.status_code == 200 and r.json()['text'] == '' and 'quota exceeded' in r.json()['error']
