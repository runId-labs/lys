"""
Agent run entity: the trace of one agent run.

Kept apart from the conversations on purpose: a run is not something the user talks in.
Stored as a conversation, it would be listed in the user's history and indexed for the
conversation search. One row per run, with what the run read and wrote (the transcript),
what it returned, and what it cost. A follow-up is a run of its own, pointing at the run it
continues: a run is never rewritten once it ended.
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.ai.modules.agent.consts import AGENT_RUN_STATUSES
from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class AIAgentRun(Entity):
    """
    One run of an agent for a user: its task, its transcript, its report, its cost.

    Written when the run starts (RUNNING) and completed when it ends (SUCCEEDED with the
    report, or FAILED with the error), so a run that dies midway still leaves its trace.
    """

    __tablename__ = "ai_agent_run"

    purpose: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="The agent's endpoint (AIConfig.endpoints key): its model, prompt and options",
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), nullable=False, index=True,
        comment="User the agent ran for, with whose rights it read (soft FK)",
    )
    client_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True,
        comment="Tenant the run was scoped to, when the caller scopes it (soft FK)",
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="RUNNING, SUCCEEDED or FAILED")
    task: Mapped[str] = mapped_column(Text, nullable=False, comment="What the agent was asked to do")
    tool_defaults: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
        comment="The run's scope, pinned in its tools; a follow-up runs on it, never on the caller's",
    )
    continued_from_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False), nullable=True, index=True,
        comment="The run this one follows up, whose transcript it continued (soft FK)",
    )
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Every message of the run: the model's calls and the tools' results",
    )
    output: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="The validated report (SUCCEEDED only)",
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Why the run failed (FAILED only)")
    calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="One entry per model call: kind (loop, report), latency_ms, tokens, tool calls asked, model",
    )
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Input tokens, cache excluded")
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Time spent waiting for the model, every call added up",
    )
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Model of the last call: after a fallback, the one that answered",
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{status}'" for status in AGENT_RUN_STATUSES) + ")",
            name="ck_ai_agent_run_status",
        ),
    )

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.user_id == user_id]
