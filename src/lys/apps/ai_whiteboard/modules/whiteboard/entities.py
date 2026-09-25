"""
Whiteboard entities.

A whiteboard is a visual working surface owned by one user. The chatbot opens one by
itself when it has something structured to show, and the user edits it by hand; both
write to the same scene.
"""

from typing import Any, Dict

from sqlalchemy import Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class Whiteboard(Entity):
    """
    An Excalidraw scene, its owner and its revision.

    The table knows nothing about conversations: a whiteboard outlives the exchange
    that produced it, and a later conversation can pick it up. The link is carried by
    ``ai_conversation.whiteboard_id`` instead — see the conversation module.
    """

    __tablename__ = "whiteboard"

    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        nullable=False,
        index=True,
        comment=(
            "Owner (soft FK - no constraint for microservices). Sole basis for access "
            "control: sharing does not exist, a whiteboard belongs to one person"
        ),
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Taken from the conversation when the chatbot opens the whiteboard itself",
    )
    # JSON and not JSONB, like every other JSON column in the framework: the scene is
    # read and written whole, never queried from the inside. Revisit only if a query
    # ever has to reach into it in SQL.
    scene_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        # A callable, not a shared dict: a mutable default would be the same object on
        # every row inserted in the process.
        default=lambda: {"elements": [], "appState": {}, "files": {}},
        comment="Excalidraw scene: elements, appState, and the files map images refer to by id",
    )
    # Two jobs, both needed. It arbitrates concurrent writes - the LLM writes server
    # side while the browser saves its debounced onChange, and last-write-wins would
    # drop one of them in silence. And it lets a client tell a missed update from an
    # applied one, since signals are never replayed.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.user_id == user_id]
