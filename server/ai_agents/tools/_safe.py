import functools
import inspect
import logging

log = logging.getLogger(__name__)


def _validate_call(fn, args, kwargs):
    sig = inspect.signature(fn)
    try:
        bound = sig.bind(*args, **kwargs)
    except TypeError as exc:
        return str(exc)
    for name, value in bound.arguments.items():
        ann = sig.parameters[name].annotation
        if ann in (str, int, float, bool) and not isinstance(value, ann):
            return 'argument %s must be %s' % (name, ann.__name__)
    return None


def _envelope(result):
    if not isinstance(result, dict):
        return {'status': 'ok', 'result': result, 'error': '', 'evidence_refs': []}
    result.setdefault('status', 'ok')
    result.setdefault('error', '')
    result.setdefault('evidence_refs', [])
    return result


def safe(fn):
    '''Turn any exception inside a tool into {'status': 'error'} so the model can recover and the turn survives.'''
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            bad = _validate_call(fn, args, kwargs)
            if bad:
                return {'status': 'error', 'error': bad, 'evidence_refs': []}
            return _envelope(fn(*args, **kwargs))
        except Exception as exc:
            log.exception('tool %s failed', fn.__name__)
            return {'status': 'error', 'error': '%s: %s' % (type(exc).__name__, exc)}
    return wrapper
