import functools
import logging

log = logging.getLogger(__name__)


def safe(fn):
    '''Turn any exception inside a tool into {'status': 'error'} so the model can recover and the turn survives.
    functools.wraps keeps the name, docstring and signature, which ADK reads to describe the tool to the model.'''
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            log.exception('tool %s failed', fn.__name__)
            return {'status': 'error', 'error': '%s: %s' % (type(exc).__name__, exc)}
    return wrapper
