"""Tiny interactive CLI for manually testing the base session loop."""

import asyncio
import sys
from time import perf_counter
from typing import TYPE_CHECKING

from rich import print as rprint
from rich.text import Text
from sqlalchemy.ext.asyncio import async_sessionmaker

from operator_core.agent.types import UserMessage
from operator_core.config import OperatorConfig, get_config
from operator_core.providers.transforms import HistoryMessageTransform
from operator_core.session.events import (
    AgentRunCancelled,
    AgentRunFailed,
    AgentRunFinished,
    AgentRunStarted,
    AgentStreamPartFinished,
    AgentStreamPartStarted,
    AgentStreamTextDelta,
    AgentStreamThinkingDelta,
    AgentStreamToolCallFinished,
    AgentStreamToolCallStarted,
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

type _HistoryEvent = (
    HistoryLoaded | SystemPromptSeeded | UserMessagePersisted | HistoryMessagePersisted
)
type _RunEvent = AgentRunStarted | AgentRunFinished | AgentRunFailed | AgentRunCancelled
type _StreamEvent = (
    AgentStreamPartStarted
    | AgentStreamTextDelta
    | AgentStreamThinkingDelta
    | AgentStreamPartFinished
    | AgentStreamToolCallStarted
    | AgentStreamToolCallFinished
)
type _TurnEvent = AgentTurnStarted | AgentTurnFinished


def main() -> None:
    """Run the interactive chat CLI using `config.toml`."""
    rprint("[bold cyan]operator-chat[/bold cyan] [dim]loading config.toml[/dim]")
    config = get_config()
    try:
        asyncio.run(run_interactive_chat(config=config))
    except KeyboardInterrupt:
        rprint("\n[yellow]interrupted[/yellow]")


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
        rprint(
            "[green]ready[/green] Type [bold]:q[/bold], [bold]:quit[/bold], "
            "quit, or exit to leave.",
        )
        rprint(f"[dim]session_id={session.session_id}[/dim]")
        while True:
            try:
                user_input = await _read_user_input("you> ")
            except EOFError:
                rprint("[yellow]bye[/yellow]")
                return
            if user_input.strip() in _EXIT_COMMANDS:
                rprint("[yellow]bye[/yellow]")
                return
            if not user_input.strip():
                continue
            event_sink.start_turn_timer()
            rprint(f"[cyan]user[/cyan] queued {len(user_input)} chars")
            messages = await session.send_user_message(UserMessage(contents=user_input))
            agent_text = _render_agent_text(messages=messages)
            streamed_text = event_sink.consume_streamed_text()
            if agent_text and not streamed_text:
                rprint(f"[bold green]agent>[/bold green] {agent_text}")
            elif not agent_text and not streamed_text:
                rprint("[bold green]agent>[/bold green] [dim]<no text response>[/dim]")
    finally:
        rprint("[blue]db[/blue] disposing engine")
        await engine.dispose()


async def _read_user_input(prompt: str) -> str:
    """Read one stdin line without creating a blocking executor thread.

    ``asyncio.to_thread(input, ...)`` leaves ``input`` blocked after cancellation, and
    ``asyncio.run`` waits for that default-executor thread during shutdown. Using the
    event loop's stdin reader lets a single Ctrl-C cancel and exit promptly.
    """
    _ = sys.stdout.write(prompt)
    _ = sys.stdout.flush()
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _on_stdin_ready() -> None:
        if future.done():
            return
        try:
            future.set_result(sys.stdin.readline())
        except Exception as error:  # noqa: BLE001 - surface stdin errors through the future
            future.set_exception(error)

    loop.add_reader(sys.stdin.fileno(), _on_stdin_ready)
    try:
        line = await future
    finally:
        _ = loop.remove_reader(sys.stdin.fileno())
    if line == "":
        raise EOFError
    return line.removesuffix("\n")


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
    _streamed_text: bool = False
    _streaming_text_open: bool = False
    _thinking_announced: bool = False
    _streaming_thinking_open: bool = False

    def start_turn_timer(self) -> None:
        self._turn_started_at = perf_counter()
        self._streamed_text = False
        self._streaming_text_open = False
        self._streaming_thinking_open = False
        self._thinking_announced = False

    def consume_streamed_text(self) -> bool:
        """Return whether text streamed during this turn and reset final-print state."""
        self._close_stream_line()
        streamed_text = self._streamed_text
        self._streamed_text = False
        return streamed_text

    async def __call__(self, *, event: SessionEvent) -> None:
        if isinstance(event, AgentTurnStarted | AgentTurnFinished):
            self._handle_turn_event(event=event)
        elif isinstance(
            event,
            HistoryLoaded | SystemPromptSeeded | UserMessagePersisted | HistoryMessagePersisted,
        ):
            self._handle_history_event(event=event)
        elif isinstance(
            event, AgentRunStarted | AgentRunFinished | AgentRunFailed | AgentRunCancelled
        ):
            self._handle_run_event(event=event)
        else:
            self._handle_stream_event(event=event)

    def _handle_turn_event(self, *, event: _TurnEvent) -> None:
        match event:
            case AgentTurnStarted(agent_id=agent_id):
                rprint(f"[blue]turn[/blue] starting agent=[bold]{agent_id}[/bold]")
            case AgentTurnFinished(persisted_message_count=persisted_message_count):
                self._close_stream_line()
                rprint(
                    "[green]turn[/green] finished "
                    f"persisted={persisted_message_count} elapsed={self._elapsed()}s",
                )

    def _handle_history_event(self, *, event: _HistoryEvent) -> None:
        match event:
            case HistoryLoaded(message_count=message_count, history_id=history_id):
                rprint(
                    "[blue]history[/blue] "
                    f"loaded {message_count} message(s) [dim]history_id={history_id}[/dim]",
                )
            case SystemPromptSeeded():
                rprint("[blue]history[/blue] seeded assembled system prompt")
            case UserMessagePersisted(author_id=author_id):
                rprint(
                    f"[blue]history[/blue] persisted user prompt author=[bold]{author_id}[/bold]"
                )
            case HistoryMessagePersisted(role=role, message_index=message_index):
                self._close_stream_line()
                rprint(
                    "[blue]history[/blue] persisted "
                    f"role=[bold]{role}[/bold] index={message_index}",
                )

    def _handle_run_event(self, *, event: _RunEvent) -> None:
        match event:
            case AgentRunStarted(replay_message_count=replay_message_count):
                rprint(
                    "[bold yellow]model[/bold yellow] request started "
                    f"[dim]replay_messages={replay_message_count}; waiting for provider...[/dim]",
                )
            case AgentRunFinished(history_request_count=history_request_count):
                self._close_stream_line()
                rprint(
                    "[bold yellow]model[/bold yellow] returned "
                    f"{history_request_count} message request(s)",
                )
            case AgentRunFailed(error_type=error_type, error_message=error_message):
                self._close_stream_line()
                rprint(f"[red]model failed[/red] {error_type}: {error_message}")
            case AgentRunCancelled():
                self._close_stream_line()
                rprint("[yellow]model run cancelled[/yellow]")

    def _handle_stream_event(self, *, event: _StreamEvent) -> None:
        match event:
            case AgentStreamPartStarted(part_kind="thinking"):
                self._print_thinking_started()
            case AgentStreamPartStarted(part_kind="tool_call"):
                self._close_stream_line()
                rprint("[magenta]tool[/magenta] model is preparing a tool call")
            case AgentStreamTextDelta(content_delta=content_delta):
                self._print_text_delta(content_delta=content_delta)
            case AgentStreamThinkingDelta(content_delta=content_delta):
                self._print_thinking_delta(content_delta=content_delta)
            case AgentStreamPartFinished(part_kind="text"):
                self._close_stream_line()
            case AgentStreamPartFinished(part_kind="thinking"):
                self._close_stream_line()
                rprint("[dim]model thinking complete[/dim]")
            case AgentStreamToolCallStarted(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                args=args,
            ):
                self._print_tool_started(tool_name=tool_name, tool_call_id=tool_call_id, args=args)
            case AgentStreamToolCallFinished(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                outcome=outcome,
                result=result,
            ):
                self._print_tool_finished(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    outcome=outcome,
                    result=result,
                )
            case _:
                pass

    def _print_thinking_started(self) -> None:
        if not self._thinking_announced:
            self._close_stream_line()
            rprint("[dim]model thinking...[/dim]")
            self._thinking_announced = True

    def _print_thinking_delta(self, *, content_delta: str) -> None:
        if not self._streaming_thinking_open:
            if not self._thinking_announced:
                self._print_thinking_started()
            self._close_stream_line()
            rprint("[dim]thinking>[/dim] ", end="")
            self._streaming_thinking_open = True
        rprint(Text(content_delta, style="dim italic"), end="")

    def _print_text_delta(self, *, content_delta: str) -> None:
        if not self._streaming_text_open:
            self._close_stream_line()
            rprint("[bold green]agent>[/bold green] ", end="")
            self._streaming_text_open = True
        rprint(Text(content_delta), end="")
        self._streamed_text = True

    def _print_tool_started(
        self,
        *,
        tool_name: str,
        tool_call_id: str,
        args: str | None,
    ) -> None:
        self._close_stream_line()
        suffix = f" args={args}" if args else ""
        rprint(
            "[magenta]tool[/magenta] calling "
            f"[bold]{tool_name}[/bold] [dim]id={tool_call_id}[/dim]{suffix}",
        )

    def _print_tool_finished(
        self,
        *,
        tool_name: str | None,
        tool_call_id: str,
        outcome: str,
        result: str | None,
    ) -> None:
        self._close_stream_line()
        suffix = f" output={result}" if result else ""
        rprint(
            "[magenta]tool[/magenta] finished "
            f"[bold]{tool_name or '<unknown>'}[/bold] "
            f"outcome={outcome} [dim]id={tool_call_id}[/dim]{suffix}",
        )

    def _close_stream_line(self) -> None:
        if self._streaming_text_open or self._streaming_thinking_open:
            rprint()
            self._streaming_text_open = False
            self._streaming_thinking_open = False

    def _elapsed(self) -> str:
        if self._turn_started_at is None:
            return "?"
        return f"{perf_counter() - self._turn_started_at:.2f}"


if __name__ == "__main__":
    main()
