"""Response models for the JARVIS HTTP API.

Every model allows extra fields (``extra='allow'``) so Unity-facing field
names that are not (yet) declared here keep flowing through unchanged.
Declared fields are type-checked; undeclared ones pass through.
"""
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, ConfigDict


class _Loose(BaseModel):
    model_config = ConfigDict(extra='allow')


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = {}


class ErrorResponse(BaseModel):
    status: Literal['error'] = 'error'
    error: ErrorDetail
    request_id: Optional[str] = None
    # Unity still reads the legacy 'detail' field on errors.
    detail: Optional[str] = None


class HealthResponse(_Loose):
    ok: bool
    repo: str
    branch: str
    changed: int
    session_backend: str          # 'sqlite' | 'memory'
    persistence_mode: str         # 'durable' | 'volatile'
    persistence_warnings: List[Dict[str, Any]] = []


class GraphResponse(_Loose):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class AskResponse(_Loose):
    reply: Optional[str] = None


class ApprovalResponse(_Loose):
    ok: Optional[bool] = None
    action: Optional[str] = None
    detail: Optional[str] = None


class PromotionResponse(_Loose):
    ok: Optional[bool] = None
    detail: Optional[str] = None


class SessionResponse(_Loose):
    session_id: str


class RepositoryListResponse(_Loose):
    active: str
    repos: List[Dict[str, Any]]


class RepositorySelectResponse(_Loose):
    active: str
    nodes: Optional[int] = None
    edges: Optional[int] = None
    session_reset_required: Optional[bool] = None


class RepositoryTreeResponse(_Loose):
    pass


class RepositoryFileResponse(_Loose):
    pass


class DesignResponse(_Loose):
    persisted: bool = True
    persistence_warning: Optional[str] = None


class ImplementationPlanResponse(_Loose):
    persisted: bool = True
    persistence_warning: Optional[str] = None


class TaskResponse(_Loose):
    busy: bool
    plan_summary: str = ''
    tasks: List[Dict[str, Any]] = []
    circular: List[Any] = []
    agent_results: List[Dict[str, Any]] = []
    findings: List[Any] = []


class ProgressResponse(_Loose):
    busy: bool
    steps: List[Dict[str, Any]] = []


class AgentListResponse(_Loose):
    agents: List[Dict[str, Any]]


class ToolListResponse(_Loose):
    tools: List[Dict[str, Any]]
