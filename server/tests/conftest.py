import os
os.environ.setdefault('JARVIS_TOKEN', 'test-token')
# A full test run creates more sessions than the default cap of 50; without
# this, /session starts returning 429 partway through and later tests fail
# with KeyError: 'session_id'.
os.environ.setdefault('JARVIS_MAX_SESSIONS', '1000')
