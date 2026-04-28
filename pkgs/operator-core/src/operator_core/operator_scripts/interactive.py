"""Tiny interactive CLI for manually testing the base session loop."""

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from rich import print as rprint
from sqlalchemy.ext.asyncio import async_sessionmaker

from operator_core.agent.types import UserMessage
from operator_core.config import OperatorConfig, get_config
from operator_core.providers.transforms import HistoryMessageTransform
from operator_core.session.events import (
    AgentRunFinished,
    AgentRunStarted,
    AgentTurnFinished,
    AgentTurnStarted,
    HistoryLoaded,
    HistoryMessagePersisted,
    SessionEvent,
    SystemPromptSeeded,
    UserMessagePersisted,
)
from operator_core.session.session import Session
from operator_db import get_db_engine
from operator_shared.providers.transforms import OperatorResponseMessage, OperatorTextPart

if TYPE_CHECKING:
    from collections.abc import Sequence

    from operator_db.objects.history.schema import HistoryMessageResponseSchema

_EXIT_COMMANDS = {":q", ":quit", "exit", "quit"}


def main() -> None:
    """Run the interactive chat CLI using `config.toml`."""
    rprint("[bold cyan]operator-chat[/bold cyan] [dim]loading config.toml[/dim]")
    config = get_config()
    asyncio.run(run_interactive_chat(config=config))


async def run_interactive_chat(*, config: OperatorConfig) -> None:
    """Create a persisted session and loop user prompts into agent responses."""
    rprint(
        "[bold cyan]operator-chat[/bold cyan] "
        f"[dim]provider={config.model.provider} model={config.model.name}[/dim]",
    )
    rprint(f"[blue]db[/blue] ensuring readiness for [dim]{config.database.url}[/dim]")
    engine = get_db_engine(config=config.database)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        event_sink = _RichSessionEventSink()
        rprint("[blue]session[/blue] creating persisted session and orchestrator agent")
        session = await Session.create(
            config=config,
            db_session=sessionmaker,
            event_sink=event_sink,
        )
        rprint("[green]ready[/green] Type [bold]:q[/bold], [bold]:quit[/bold], quit, or exit to leave.")
        rprint(f"[dim]session_id={session.session_id}[/dim]")
        while True:
            user_input = await asyncio.to_thread(input, "you> ")
            if user_input.strip() in _EXIT_COMMANDS:
                rprint("[yellow]bye[/yellow]")
                return
            if not user_input.strip():
                continue
            event_sink.start_turn_timer()
            rprint(f"[cyan]user[/cyan] queued {len(user_input)} chars")
            messages = await session.send_user_message(UserMessage(contents=user_input))
            agent_text = _render_agent_text(messages=messages)
            if agent_text:
                rprint(f"[bold green]agent>[/bold green] {agent_text}")
            else:
                rprint("[bold green]agent>[/bold green] [dim]<no text response>[/dim]")
    finally:
        rprint("[blue]db[/blue] disposing engine")
        await engine.dispose()


def _render_agent_text(*, messages: Sequence[HistoryMessageResponseSchema]) -> str | None:
    transform = HistoryMessageTransform()
    text_parts: list[str] = []
    for message in transform.to_operator_messages(messages=messages):
        if not isinstance(message, OperatorResponseMessage):
            continue
        text_parts.extend(
            part.content for part in message.parts if isinstance(part, OperatorTextPart)
        )
    if not text_parts:
        return None
    return "\n".join(text_parts)


class _RichSessionEventSink:
    _turn_started_at: float | None = None

    def start_turn_timer(self) -> None:
        self._turn_started_at = perf_counter()

    async def __call__(self, *, event: SessionEvent) -> None:
        match event:
            case AgentTurnStarted(agent_id=agent_id):
                rprint(f"[blue]turn[/blue] starting agent=[bold]{agent_id}[/bold]")
            case HistoryLoaded(message_count=message_count, history_id=history_id):
                rprint(
                    "[blue]history[/blue] "
                    f"loaded {message_count} message(s) [dim]history_id={history_id}[/dim]",
                )
            case SystemPromptSeeded():
                rprint("[blue]history[/blue] seeded assembled system prompt")
            case UserMessagePersisted(author_id=author_id):
                rprint(f"[blue]history[/blue] persisted user prompt author=[bold]{author_id}[/bold]")
            case AgentRunStarted(replay_message_count=replay_message_count):
                rprint(
                    "[bold yellow]model[/bold yellow] request started "
                    f"[dim]replay_messages={replay_message_count}; waiting for provider...[/dim]",
                )
            case AgentRunFinished(history_request_count=history_request_count):
                rprint(
                    "[bold yellow]model[/bold yellow] returned "
                    f"{history_request_count} message request(s)",
                )
            case HistoryMessagePersisted(role=role, message_index=message_index):
                rprint(
                    "[blue]history[/blue] persisted "
                    f"role=[bold]{role}[/bold] index={message_index}",
                )
            case AgentTurnFinished(persisted_message_count=persisted_message_count):
                rprint(
                    "[green]turn[/green] finished "
                    f"persisted={persisted_message_count} elapsed={self._elapsed()}s",
                )

    def _elapsed(self) -> str:
        if self._turn_started_at is None:
            return "?"
        return f"{perf_counter() - self._turn_started_at:.2f}"


if __name__ == "__main__":
    main()
