"""Postgres (or any SQLAlchemy database) store for design docs and revision history.

Enabled by setting JARVIS_DESIGN_DB to a *synchronous* SQLAlchemy URL, e.g.
    postgresql+psycopg2://user:pass@host:5432/jarvis
When it is unset, architecture_tools keeps using the JSON files in data/design/.

Two tables, created on first use (use Alembic for later schema changes):
    jarvis_designs         one row per session: owner, current revision, JSON doc
    jarvis_design_history  one row per archived revision of a session
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, create_engine,
                        delete, select)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

log = logging.getLogger(__name__)

_JSON = JSON().with_variant(JSONB(), 'postgresql')
_meta = MetaData()

designs = Table(
    'jarvis_designs', _meta,
    Column('session_id', String(128), primary_key=True),
    Column('owner', String(64), nullable=False, server_default=''),
    Column('revision', Integer, nullable=False, server_default='0'),
    Column('doc', _JSON, nullable=False),
    Column('updated_at', Float, nullable=False),
)
history = Table(
    'jarvis_design_history', _meta,
    Column('session_id', String(128), primary_key=True),
    Column('revision', Integer, primary_key=True),
    Column('doc', _JSON, nullable=False),
    Column('saved_at', Float, nullable=False),
)

_engine = None
_engine_url = None
_lock = threading.Lock()


def url() -> Optional[str]:
    return os.getenv('JARVIS_DESIGN_DB') or None


def enabled() -> bool:
    return bool(url())


def engine():
    """Lazily create the engine (and tables) for the current JARVIS_DESIGN_DB."""
    global _engine, _engine_url
    u = url()
    with _lock:
        if _engine is None or _engine_url != u:
            if _engine is not None:
                _engine.dispose()
            _engine = None
            eng = create_engine(u, pool_pre_ping=True, pool_size=5, max_overflow=5)
            try:
                _meta.create_all(eng)          # fails fast if the database is unreachable
            except Exception:
                eng.dispose()
                raise                          # nothing half-initialised stays cached
            _engine, _engine_url = eng, u
    return _engine


def _revision_of(doc: Dict[str, Any]) -> int:
    try:
        return int(((doc or {}).get('architecture') or {}).get('revision') or 0)
    except (TypeError, ValueError):
        return 0


def get_row(session_id: str) -> Optional[Dict[str, Any]]:
    with engine().connect() as c:
        r = c.execute(select(designs).where(designs.c.session_id == session_id)).first()
    return dict(r._mapping) if r else None


def load(session_id: str) -> Dict[str, Any]:
    row = get_row(session_id)
    return row['doc'] if row else {}


def owner(session_id: str) -> Optional[str]:
    """None when no design exists; '' for a legacy ownerless row; else the owner."""
    row = get_row(session_id)
    return None if row is None else (row['owner'] or '')


def save(session_id: str, payload: Dict[str, Any], owner_provider) -> bool:
    """Atomic upsert. The row is locked (SELECT ... FOR UPDATE) so two writers of the
    same session serialise; the replaced revision is archived in the same transaction."""
    now = time.time()
    with engine().begin() as c:
        old = c.execute(select(designs).where(designs.c.session_id == session_id)
                        .with_for_update()).first()
        old_owner = (old.owner if old else '') or ''
        own = old_owner or owner_provider() or ''           # ownership is sticky
        payload = dict(payload)
        if own:
            payload['_owner'] = own
        new_rev = _revision_of(payload)
        if old is not None:
            old_rev = _revision_of(old.doc)
            if old_rev and old_rev != new_rev:
                stmt = _insert(history).values(session_id=session_id, revision=old_rev,
                                               doc=old.doc, saved_at=now)
                c.execute(stmt.on_conflict_do_update(
                    index_elements=['session_id', 'revision'],
                    set_={'doc': old.doc, 'saved_at': now}))
        stmt = _insert(designs).values(session_id=session_id, owner=own, revision=new_rev,
                                       doc=payload, updated_at=now)
        c.execute(stmt.on_conflict_do_update(
            index_elements=['session_id'],
            set_={'owner': own, 'revision': new_rev, 'doc': payload, 'updated_at': now}))
    return True


def _insert(table):
    """Dialect-appropriate INSERT supporting ON CONFLICT (Postgres and SQLite)."""
    if engine().dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(table)


def list_versions(session_id: str) -> List[Dict[str, Any]]:
    with engine().connect() as c:
        rows = c.execute(select(history.c.revision, history.c.saved_at)
                         .where(history.c.session_id == session_id)
                         .order_by(history.c.revision)).all()
    return [{'revision': r.revision, 'saved_at': r.saved_at} for r in rows]


def load_version(session_id: str, revision: int) -> Dict[str, Any]:
    with engine().connect() as c:
        r = c.execute(select(history.c.doc).where(
            history.c.session_id == session_id, history.c.revision == int(revision))).first()
    return r.doc if r else {}


def delete_all(session_id: str) -> None:
    with engine().begin() as c:
        c.execute(delete(history).where(history.c.session_id == session_id))
        c.execute(delete(designs).where(designs.c.session_id == session_id))
