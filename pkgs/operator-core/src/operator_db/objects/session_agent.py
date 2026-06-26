from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.objects import HistoryEvent
from operator_db.objects.history_epoch import HistoryEpochSvc
from operator_shared.constants import ORCHESTRATOR_AGENT_ID

from .base import Base, IDType, Repo, Svc
from .constants import TxtShort  # noqa: TC001
from .mail import MailMapping
from .types import MsgRole

if TYPE_CHECKING:
    from pydantic import JsonValue

    from .history import History
    from .session import Session


class SessionAgent(Base):
    __tablename__ = "session_agents"

    agent_id: Mapped[TxtShort] = mapped_column(index=True)

    # IMPORTANT:
    # We only set `history_id` for the *main* or initial branch.
    # Any forks and their relations go into History.forked_from_id
    history_id: Mapped[IDType] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
    )
    history: Mapped[History] = relationship(
        uselist=False,
        back_populates="session_agent",
        lazy="immediate",
    )

    session_id: Mapped[IDType] = mapped_column(
        ForeignKey("sessions.id"),
        index=True,
    )
    session: Mapped[Session] = relationship(
        uselist=False,
        back_populates="session_agents",
        lazy="immediate",
    )

    mail_sent: Mapped[list[MailMapping]] = relationship(
        back_populates="sender",
        foreign_keys=lambda: [MailMapping.sender_id],
    )
    mail_received: Mapped[list[MailMapping]] = relationship(
        back_populates="receiver",
        foreign_keys=lambda: [MailMapping.receiver_id],
    )

    async def as_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        mail_sent: list[MailMapping] = await self._at.mail_sent
        mail_received: list[MailMapping] = await self._at.mail_received
        return {
            "agent_id": await self._at.agent_id,
            "history": await (await self._at.history).as_dict(),
            "mail_sent": [await x.as_dict() for x in mail_sent],
            "mail_received": [await x.as_dict() for x in mail_received],
        }


class SessionAgentRepo(Repo[SessionAgent]):
    model_type = SessionAgent


class SessionAgentSvc(Svc[SessionAgent]):
    repository_type = SessionAgentRepo

    @property
    def _epoch_svc(self) -> HistoryEpochSvc:
        return self._get_svc(HistoryEpochSvc)

    def _bake_initial_events(
        self,
        *,
        system_prompt: str,
        model_name: str,
        model_provider: str,
        permissions: dict[str, Any],
    ) -> list[HistoryEvent.Type]:
        """Make initial set of events for the first epoch of a history."""
        return [
            HistoryEvent.ChatStart(),
            HistoryEvent.Message(role=MsgRole.SYSTEM, text=system_prompt),
            HistoryEvent.UsePermissions(data=permissions),
            HistoryEvent.UseModel(model_name=model_name, model_provider=model_provider),
        ]

    def bake_orchestrator_agent(
        self,
        *,
        agent_id: str = ORCHESTRATOR_AGENT_ID,
        system_prompt: str,
        model_name: str,
        model_provider: str,
        permissions: dict[str, Any],
    ) -> dict[str, Any]:
        """Bake data for making an orchestrator agent as part of a larger query."""
        return {
            "agent_id": agent_id,
            "history": {
                "epochs": [
                    {
                        "events": self._bake_initial_events(
                            system_prompt=system_prompt,
                            model_name=model_name,
                            model_provider=model_provider,
                            permissions=permissions,
                        ),
                    }
                ]
            },
        }

    async def add_message(
        self,
        *,
        history: History,
        text_data: str | None = None,
        json_data: JsonValue | None = None,
        bytes_data: bytes | None = None,
        role: MsgRole = MsgRole.USER,
    ) -> None:
        """Add a message."""
        epoch = await history.get_current_epoch(self._session)
        msg_ev = HistoryEvent.Message(
            role=role,
            text=text_data,
            json=json_data,
            binary_contents=bytes_data,
            epoch_id=epoch.id,
        )
        self._session.add(msg_ev)
        await self._session.commit()

    async def make_agent(
        self,
        *,
        session_id: IDType,
        agent_id: str,
        initial_prompt: str | None = None,
    ) -> SessionAgent: ...
