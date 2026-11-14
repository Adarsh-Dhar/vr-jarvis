"""Lease-based session management for JARVIS sessions.

Sessions are leased, not merely timestamped: a lease records which
holder owns the session, when it was last renewed, and when it expires.
Eviction and repository-switch guards only consider sessions whose lease
is live; expired leases are treated as abandoned and may be collected.

The lease record lives inside the ADK session state under
``_lease`` so it persists with the session on BOTH backends (sqlite and
in-memory) without a separate table. ``migrate_legacy_sessions`` upgrades
pre-lease sessions on first access.
"""
import time
import uuid
from typing import Any, Dict, Optional

LEASE_STATE_KEY = '_lease'
DEFAULT_TTL_SECONDS = 300.0


def _now() -> float:
    return time.time()


class SessionLeaseManager:
    """Acquire, renew and inspect leases stored in session state."""

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self.ttl = float(ttl_seconds)

    # -- state helpers -------------------------------------------------
    @staticmethod
    def _lease_of(session) -> Optional[Dict[str, Any]]:
        state = getattr(session, 'state', None) or {}
        lease = state.get(LEASE_STATE_KEY)
        return lease if isinstance(lease, dict) else None

    @staticmethod
    def _write_lease(session_service, session, lease: Dict[str, Any]):
        """Persist the lease through an event state_delta so both the
        sqlite and memory backends store it durably."""
        import asyncio
        from google.adk.events import Event, EventActions

        async def _append():
            await session_service.append_event(
                session,
                Event(author='system',
                      actions=EventActions(
                          state_delta={LEASE_STATE_KEY: lease})))
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_append())
        else:
            # Caller is inside a loop: schedule and let the caller await
            # via the returned coroutine is not possible here, so fall
            # back to a dedicated loop only when truly synchronous use
            # is detected. Async callers should use acquire_async.
            raise RuntimeError(
                'use acquire_async/renew_async inside an event loop')

    # -- lease lifecycle ------------------------------------------------
    def is_active(self, session) -> bool:
        lease = self._lease_of(session)
        if not lease:
            return False
        return float(lease.get('expires_at', 0)) > _now()

    def holder(self, session) -> Optional[str]:
        lease = self._lease_of(session)
        return lease.get('holder') if lease else None

    async def acquire_async(self, session_service, session,
                            holder: Optional[str] = None) -> Dict[str, Any]:
        """Take or renew the lease on ``session``. Returns the lease dict.
        A lease held by a different live holder is NOT stolen — the
        caller gets the existing lease with ``acquired=False``."""
        holder = holder or uuid.uuid4().hex
        now = _now()
        existing = self._lease_of(session)
        if existing and float(existing.get('expires_at', 0)) > now \
                and existing.get('holder') != holder:
            return dict(existing, acquired=False)
        lease = {'holder': holder, 'acquired_at': now,
                 'renewed_at': now, 'expires_at': now + self.ttl}
        await session_service.append_event(
            session, _lease_event(lease))
        # Keep the in-memory view coherent for callers that read state
        # before the event is folded back in.
        session.state[LEASE_STATE_KEY] = lease
        return dict(lease, acquired=True)

    async def renew_async(self, session_service, session,
                          holder: Optional[str] = None) -> bool:
        """Extend the lease. Only the current holder may renew."""
        existing = self._lease_of(session)
        now = _now()
        if not existing or float(existing.get('expires_at', 0)) <= now:
            return False
        if holder is not None and existing.get('holder') != holder:
            return False
        lease = dict(existing, renewed_at=now,
                     expires_at=now + self.ttl)
        await session_service.append_event(session, _lease_event(lease))
        session.state[LEASE_STATE_KEY] = lease
        return True

    async def release_async(self, session_service, session,
                            holder: Optional[str] = None) -> bool:
        """Drop the lease. Only the holder (or an expired lease) may
        release; releasing someone else's live lease returns False."""
        existing = self._lease_of(session)
        if not existing:
            return False
        now = _now()
        live = float(existing.get('expires_at', 0)) > now
        if live and holder is not None \
                and existing.get('holder') != holder:
            return False
        lease = dict(existing, holder=None,
                     expires_at=min(float(existing.get('expires_at', 0)),
                                    now))
        await session_service.append_event(session, _lease_event(lease))
        session.state[LEASE_STATE_KEY] = lease
        return True


def _lease_event(lease: Dict[str, Any]):
    from google.adk.events import Event, EventActions
    return Event(author='system',
                 actions=EventActions(
                     state_delta={LEASE_STATE_KEY: lease}))


async def migrate_legacy_sessions(session_service, app_name: str,
                                  user_id: str,
                                  list_sessions,
                                  ttl_seconds: float = DEFAULT_TTL_SECONDS
                                  ) -> int:
    """One-time migration: every persisted session without a lease record
    gets an initial lease so pre-lease state is never treated as
    unowned-and-abandoned. Returns the number of sessions migrated."""
    migrated = 0
    manager = SessionLeaseManager(ttl_seconds)
    resp = await list_sessions(app_name=app_name, user_id=user_id)
    for session in getattr(resp, 'sessions', None) or []:
        if manager._lease_of(session) is not None:
            continue
        lease = {'holder': 'legacy', 'acquired_at': _now(),
                 'renewed_at': _now(),
                 'expires_at': _now() + ttl_seconds,
                 'migrated': True}
        await session_service.append_event(session, _lease_event(lease))
        try:
            session.state[LEASE_STATE_KEY] = lease
        except Exception:
            pass
        migrated += 1
    return migrated
