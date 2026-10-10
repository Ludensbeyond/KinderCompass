"""Opt-in, bounded ephemeral dialogue; independent of preference persistence."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Callable
from uuid import UUID, uuid4

from SystemCode.src.backend.agents.contracts import ConversationExchange


class ConversationHistoryConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoryLease:
    session_id: str
    token: str
    exchanges: tuple[ConversationExchange, ...]
    omitted: bool


@dataclass
class _Session:
    touched: float
    exchanges: list[ConversationExchange] = field(default_factory=list)
    omitted: bool = False
    token: str | None = None
    profile: dict | None = None


class ConversationHistoryService:
    def __init__(self, *, clock: Callable[[], float] = monotonic,
                 ttl_seconds: float = 1800, max_sessions: int = 1000):
        if ttl_seconds <= 0 or max_sessions < 1:
            raise ValueError("History retention and capacity must be positive")
        self._clock = clock
        self._ttl = ttl_seconds
        self._capacity = max_sessions
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def _id(session_id: UUID | str) -> str:
        return str(UUID(str(session_id)))

    def _expire(self, now: float) -> None:
        for key in list(self._sessions):
            if now - self._sessions[key].touched >= self._ttl:
                del self._sessions[key]

    def begin(self, session_id: UUID | str | None, *, retain: bool = False) -> HistoryLease | None:
        if not retain:
            return None
        if session_id is None:
            raise ValueError("An anonymous session ID is required to retain conversation")
        key = self._id(session_id)
        with self._lock:
            now = self._clock()
            self._expire(now)
            session = self._sessions.get(key)
            if session is None:
                if len(self._sessions) >= self._capacity:
                    idle = next((k for k, s in self._sessions.items() if s.token is None), None)
                    if idle is None:
                        raise ConversationHistoryConflict("Conversation history capacity is busy")
                    del self._sessions[idle]
                session = _Session(now)
                self._sessions[key] = session
            if session.token is not None:
                raise ConversationHistoryConflict("A conversation turn is already in progress")
            session.token = str(uuid4())
            session.touched = now
            self._sessions.move_to_end(key)
            return HistoryLease(key, session.token,
                                tuple(e.model_copy(deep=True) for e in session.exchanges),
                                session.omitted)

    def begin_turn(self, session_id, *, profile: dict, retain: bool) -> HistoryLease | None:
        if session_id is None:
            return self.begin(None, retain=retain)
        lease = self.begin(session_id, retain=True)
        with self._lock:
            session = self._sessions.get(lease.session_id)
            if session is None or session.token != lease.token:
                raise ConversationHistoryConflict("Conversation lease was forgotten")
            if session.profile is not None and session.profile != profile:
                session.token = None
                raise ConversationHistoryConflict("Submitted preference state is stale")
        return lease if retain else HistoryLease(lease.session_id, lease.token, (), False)

    def commit(self, lease: HistoryLease, *, message: str, answer: str,
               profile: dict | None = None, retain: bool = True,
               before_commit: Callable[[], None] | None = None) -> None:
        exchange = ConversationExchange(user=message, assistant=answer) if retain else None
        detached = deepcopy(profile)
        with self._lock:
            self._expire(self._clock())
            session = self._sessions.get(lease.session_id)
            if session is None or session.token != lease.token:
                raise ConversationHistoryConflict("Conversation lease expired or was forgotten")
            if before_commit:
                before_commit()
            if exchange:
                session.exchanges.append(exchange)
            while len(session.exchanges) > 6 or sum(
                len(e.user) + len(e.assistant) for e in session.exchanges
            ) > 8000:
                session.exchanges.pop(0)
                session.omitted = True
            session.token = None
            if detached is not None:
                session.profile = detached
            session.touched = self._clock()
            self._sessions.move_to_end(lease.session_id)

    def abort(self, lease: HistoryLease | None) -> None:
        if lease is None:
            return
        with self._lock:
            session = self._sessions.get(lease.session_id)
            if session is not None and session.token == lease.token:
                session.token = None

    def forget(self, session_id: UUID | str, *, after_forget: Callable[[], None] | None = None) -> None:
        with self._lock:
            self._sessions.pop(self._id(session_id), None)
            if after_forget:
                after_forget()
