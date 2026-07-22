"""Interactive CLI for exercising the persisted session loop."""

import asyncio
import sys
from time import perf_counter
from typing import TYPE_CHECKING, override

from attrs import Factory, define, field
from rich.console import Console
from rich.live import Live
from rich.text import Text

from operator_core.session.events import (
  AgentPartEnd,
  AgentPartStart,
  AgentRunFail,
  AgentTextDelta,
  AgentThinkingDelta,
  AgentToolCallEnd,
  AgentToolCallStart,
  AgentTurnEnd,
  AgentTurnStart,
  SessionEventSink,
  SessionEventType,
)
from operator_core.session.main import SessionManager
from operator_core.session.types import IncomingMessage
from operator_db.connection.ensure_db import ensure_db_ready
from operator_db.connection.main import (
  get_async_engine,
  get_sessionmaker,
)
from operator_shared.constants import ORCHESTRATOR_AGENT_ID
from operator_shared.settings.loader import load_operator_settings

if TYPE_CHECKING:
  from asyncio import Future

  from operator_shared.settings.main import OperatorSettings

_EXIT_COMMANDS = {":q", ":quit", "exit", "quit"}


@define
class _RichSessionEventSink(SessionEventSink):
  """Render session events synchronously with Rich."""

  console: Console = Factory(Console)
  _parts: dict[int, str] = field(init=False, factory=dict)
  _live: Live | None = field(init=False, default=None)
  _live_part_index: int | None = field(init=False, default=None)
  _turn_started_at: float | None = field(init=False, default=None)
  _text_seen: bool = field(init=False, default=False)

  @override
  def handle(self, event: SessionEventType) -> None:
    """Render one session event."""
    match event:
      case AgentTurnStart() | AgentTurnEnd():
        self._handle_turn(event)
      case AgentPartStart(part_index=part_index):
        self._parts.pop(part_index, None)
      case AgentPartEnd(part_index=part_index):
        if self._live_part_index == part_index:
          self._close_live()
      case AgentTextDelta() | AgentThinkingDelta():
        self._handle_delta(event)
      case AgentToolCallStart() | AgentToolCallEnd():
        self._handle_tool(event)
      case AgentRunFail() as failure:
        self._close_live()
        self.console.print(
          Text(
            f"model failed {failure.error_type}: "
            f"{failure.error_message}",
            style="red",
          )
        )

  def _handle_turn(
    self, event: AgentTurnStart | AgentTurnEnd
  ) -> None:
    match event:
      case AgentTurnStart(agent_id=agent_id):
        self._close_live()
        self._parts.clear()
        self._text_seen = False
        self._turn_started_at = perf_counter()
        self.console.print(
          Text.assemble(
            ("turn ", "blue"),
            "starting agent=",
            (agent_id, "bold"),
          )
        )
      case AgentTurnEnd():
        self._close_live()
        if not self._text_seen:
          self.console.print(
            Text.assemble(
              ("agent> ", "bold green"),
              ("<no text response>", "dim"),
            )
          )
        self.console.print(
          Text.assemble(
            ("turn ", "green"),
            f"finished elapsed={self._elapsed()}s",
          )
        )

  def _handle_delta(
    self, event: AgentTextDelta | AgentThinkingDelta
  ) -> None:
    match event:
      case AgentTextDelta():
        self._text_seen |= bool(event.content)
        thinking = False
      case AgentThinkingDelta():
        thinking = True
    self._update_part(
      part_index=event.part_index,
      content=event.content,
      replace=event.replace,
      thinking=thinking,
    )

  def _handle_tool(
    self, event: AgentToolCallStart | AgentToolCallEnd
  ) -> None:
    self._close_live()
    name = event.tool_name or "<unknown>"
    match event:
      case AgentToolCallStart():
        message = Text.assemble(
          ("tool ", "magenta"),
          "calling ",
          (name, "bold"),
          f" id={event.tool_call_id} args={event.args!r}",
        )
      case AgentToolCallEnd():
        message = Text.assemble(
          ("tool ", "magenta"),
          "finished ",
          (name, "bold"),
          f" outcome={event.outcome} id={event.tool_call_id}",
          f" result={event.result!r}",
        )
    self.console.print(message)

  def _update_part(
    self,
    *,
    part_index: int,
    content: str | None,
    replace: bool,
    thinking: bool,
  ) -> None:
    previous = self._parts.get(part_index, "")
    current = (
      (content or "") if replace else previous + (content or "")
    )
    self._parts[part_index] = current

    if self._live_part_index != part_index:
      self._close_live()
      self._live_part_index = part_index
      self._live = Live(console=self.console, refresh_per_second=20)
      self._live.start()

    rendered = Text(
      "thinking> " if thinking else "agent> ",
      style="dim" if thinking else "bold green",
    )
    rendered.append(current, style="dim italic" if thinking else None)
    if self._live:
      self._live.update(rendered, refresh=True)

  def _close_live(self) -> None:
    if self._live:
      self._live.stop()
      self.console.print()
    self._live = None
    self._live_part_index = None

  def _elapsed(self) -> str:
    if self._turn_started_at is None:
      return "?"
    return f"{perf_counter() - self._turn_started_at:.2f}"


def main() -> None:
  """Run the interactive chat CLI using ``config.toml``."""
  console = Console()
  console.print(
    Text.assemble(
      ("operator-chat", "bold cyan"),
      (" loading config.toml", "dim"),
    )
  )
  settings = load_operator_settings()
  console.print(Text("db ensuring readiness", style="blue"))
  ensure_db_ready(settings)
  try:
    asyncio.run(
      run_interactive_chat(settings=settings, console=console)
    )
  except KeyboardInterrupt:
    console.print(Text("\ninterrupted", style="yellow"))


async def run_interactive_chat(
  *,
  settings: OperatorSettings,
  console: Console | None = None,
) -> None:
  """Run a persisted session and loop prompts into the agent."""
  console = console or Console()
  engine = get_async_engine(settings)
  sessionmaker = get_sessionmaker(engine, expire_on_commit=False)
  try:
    async with sessionmaker() as db_session:
      sink = _RichSessionEventSink(console=console)
      session = SessionManager(
        settings=settings,
        db_session=db_session,
        event_sink=sink,
      )
      await session.refresh_agents()
      console.print(
        Text.assemble(
          ("ready", "green"),
          " Type :q, :quit, quit, or exit to leave.",
        )
      )
      while True:
        try:
          user_input = await _read_user_input("you> ")
        except EOFError:
          console.print(Text("bye", style="yellow"))
          return
        if user_input.strip() in _EXIT_COMMANDS:
          console.print(Text("bye", style="yellow"))
          return
        if not user_input.strip():
          continue
        await session.add_user_message(
          agent_id=ORCHESTRATOR_AGENT_ID,
          message=IncomingMessage(text_data=user_input),
        )
        _ = await session.do_agent_loop(ORCHESTRATOR_AGENT_ID)
  finally:
    await engine.dispose()


async def _read_user_input(prompt: str) -> str:
  """Read one stdin line without blocking the event loop."""
  _ = sys.stdout.write(prompt)
  _ = sys.stdout.flush()
  loop = asyncio.get_running_loop()
  future: Future[str] = loop.create_future()

  def on_stdin_ready() -> None:
    if not future.done():
      future.set_result(sys.stdin.readline())

  loop.add_reader(sys.stdin.fileno(), on_stdin_ready)
  try:
    line = await future
  finally:
    _ = loop.remove_reader(sys.stdin.fileno())
  if not line:
    raise EOFError
  return line.removesuffix("\n")


if __name__ == "__main__":
  main()
