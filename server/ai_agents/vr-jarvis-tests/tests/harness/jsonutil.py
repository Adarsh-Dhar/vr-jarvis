import json
import re

ID_RE = re.compile(r'\b(?:api|auth|db|util|orphan)\.[A-Za-z]+\b')


def extract_json(text):
    '''Best-effort parse of a JSON object from model text (handles code fences and prose around it).'''
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    t = text.strip()
    t = re.sub(r'^```(?:json)?', '', t).strip()
    t = re.sub(r'```$', '', t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    a, b = t.find('{'), t.rfind('}')
    if a != -1 and b > a:
        try:
            return json.loads(t[a:b + 1])
        except Exception:
            return None
    return None


def ids_in_text(text):
    seen, out = set(), []
    for m in ID_RE.findall(text or ''):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out
