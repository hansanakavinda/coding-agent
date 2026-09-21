"""Command-line interface for the coding agent."""

import os
from pathlib import Path
import sys
from typing import Annotated, Any, Optional

# Ensure standard output streams support UTF-8 on Windows
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import completion_is_selected, has_completions
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
import typer

from core.loop import AgentLoop
from core.types import AgentStep, ConfirmationCallback
from memory.config import ConfigManager, is_valid_api_key
from memory.session import SessionManager
from providers.openrouter import DEFAULT_MODEL, OpenRouterProvider
from tools import get_default_registry

# Automatically search and load .env from current directory or parent directories
load_dotenv()

app = typer.Typer(
    help="Autonomous CLI Coding Agent built from scratch for OpenRouter free models.",
    add_completion=False,
)
console = Console(highlight=False)


class StatusManager:
    """Manages animated terminal status and spinner for background agent processing."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._status = None

    def update(self, message: str | None) -> None:
        """Show, update, or stop the status indicator."""
        if message:
            if self._status is None:
                self._status = self.console.status(f"[bold cyan]{message}[/]", spinner="dots")
                self._status.start()
            else:
                self._status.update(f"[bold cyan]{message}[/]")
        else:
            self.stop()

    def stop(self) -> None:
        """Safely stop and clear the active status indicator."""
        if self._status is not None:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None

    def is_active(self) -> bool:
        """Check whether a status spinner is currently active."""
        return self._status is not None


def render_step(step: AgentStep) -> None:
    """Format and display agent steps with rich styling."""
    if step.kind == "thought":
        model_name = step.payload.get("model", "unknown")
        content = step.payload.get("content", "").strip()
        console.print(
            Panel(
                content,
                title=f"[cyan][Thinking][/] [dim]({model_name})[/]",
                border_style="cyan",
            )
        )
    elif step.kind == "tool_call":
        name = step.payload.get("name")
        args = step.payload.get("arguments")
        console.print(
            Panel(
                f"[bold cyan]Action:[/] {name}\n[bold cyan]Arguments:[/] {args}",
                title=f"[yellow][Tool Call: {name}][/]",
                border_style="yellow",
            )
        )
    elif step.kind == "tool_result":
        name = step.payload.get("name")
        success = step.payload.get("success", False)
        output = step.payload.get("output", "")
        error = step.payload.get("error")

        if success:
            console.print(
                Panel(
                    output,
                    title=f"[green][Tool Result: {name}][/]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[red]{error}[/]",
                    title=f"[red][Tool Error: {name}][/]",
                    border_style="red",
                )
            )
    elif step.kind == "final_answer":
        model_name = step.payload.get("model", "unknown")
        content = step.payload.get("content", "").strip()
        console.print(
            Panel(
                Markdown(content),
                title=f"[bold green][Final Answer][/] [dim]({model_name})[/]",
                border_style="green",
            )
        )


def handle_fallback(failed_model: str, error: Exception | str) -> None:
    """Notify user when a candidate model fails and fallback is triggered."""
    console.print(
        f"[yellow][WARN] Model '{failed_model}' failed ({error}). Falling back to next candidate...[/]"
    )


def prompt_action_confirmation(action: str, options: list[str]) -> int:
    """Prompt user to select a confirmation option using 1/2/3, y/n, or arrow keys."""
    if not sys.stdin.isatty():
        choice = Prompt.ask(
            f"[bold]Approve [cyan]{action}[/]? (1=Yes, 2=No, 3=Always)[/]",
            choices=["1", "2", "3"],
            default="1",
        )
        return int(choice) - 1

    selected_idx = [0]

    def get_formatted_text():
        tokens = [
            ("bold", f"\nSelect an action for {action} "),
            ("dim", "(Use ↑/↓ arrows or press 1-3, then Enter):\n"),
        ]
        for i, opt in enumerate(options):
            if i == selected_idx[0]:
                tokens.append(("class:selected", f"  ❯ {opt}\n"))
            else:
                tokens.append(("class:unselected", f"    {opt}\n"))
        return tokens

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        selected_idx[0] = (selected_idx[0] - 1) % len(options)

    @kb.add("down")
    def _down(event):
        selected_idx[0] = (selected_idx[0] + 1) % len(options)

    @kb.add("1")
    @kb.add("y")
    def _opt1(event):
        selected_idx[0] = 0
        event.app.exit(result=0)

    @kb.add("2")
    @kb.add("n")
    def _opt2(event):
        selected_idx[0] = 1
        event.app.exit(result=1)

    @kb.add("3")
    def _opt3(event):
        selected_idx[0] = 2
        event.app.exit(result=2)

    @kb.add("enter")
    def _enter(event):
        event.app.exit(result=selected_idx[0])

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        event.app.exit(result=1)

    style = Style.from_dict({
        "selected": "bold #00d7ff",
        "unselected": "#bbbbbb",
    })

    try:
        output = None
        try:
            from prompt_toolkit.output.defaults import create_output
            output = create_output()
        except Exception:
            from prompt_toolkit.output.vt100 import Vt100_Output
            output = Vt100_Output(sys.stdout, lambda: (80, 24))

        app = Application(
            layout=Layout(HSplit([Window(content=FormattedTextControl(get_formatted_text))])),
            key_bindings=kb,
            style=style,
            full_screen=False,
            erase_when_done=False,
            output=output,
        )
        res = app.run()
        return res if res is not None else 1
    except Exception:
        choice = Prompt.ask(
            f"[bold]Approve [cyan]{action}[/]? (1=Yes, 2=No, 3=Always)[/]",
            choices=["1", "2", "3"],
            default="1",
        )
        return int(choice) - 1


def make_confirmation_callback(auto_approve: bool) -> ConfirmationCallback | None:
    """Create user confirmation prompt handler with 1/2/3 and arrow-key selection."""
    if auto_approve:
        return None

    session_state = {"always_allow": False}

    def confirm(action: str, details: str) -> bool:
        if session_state["always_allow"]:
            return True

        if action == "edit_file":
            title = "[yellow]Confirm File Edit (Unified Diff)[/]"
            border_style = "yellow"
            options = [
                "1. Yes, apply this edit",
                "2. No, reject this edit",
                "3. Always allow edits for this session",
            ]
        elif action == "write_file":
            title = "[yellow]Confirm File Write (Preview)[/]"
            border_style = "yellow"
            options = [
                "1. Yes, write this file",
                "2. No, cancel file write",
                "3. Always allow writes for this session",
            ]
        elif action == "run_bash":
            title = "[red]Confirm Shell Execution[/]"
            border_style = "red"
            options = [
                "1. Yes, run this command",
                "2. No, skip this command",
                "3. Always allow commands for this session",
            ]
        else:
            title = f"[yellow]Confirm Action: {action}[/]"
            border_style = "yellow"
            options = [
                f"1. Yes, execute {action}",
                f"2. No, cancel {action}",
                f"3. Always allow for this session",
            ]

        console.print(Panel(details, title=title, border_style=border_style))
        selection = prompt_action_confirmation(action, options)

        if selection == 2:
            session_state["always_allow"] = True
            console.print("[green]✓ Auto-approve enabled for the rest of this session.[/]\n")
            return True
        elif selection == 0:
            return True
        else:
            console.print(f"[yellow]Cancelled {action}.[/]\n")
            return False

    return confirm


def resolve_api_key(config_mgr: ConfigManager) -> str:
    """Obtain OpenRouter API key from env, global config, or interactive prompt."""
    api_key = config_mgr.get_api_key()
    if api_key:
        return api_key

    console.print(
        Panel(
            "[bold cyan]Welcome to Free Coding Agent![/]\n\n"
            "To get started, you need an OpenRouter API key (free tier available).\n"
            "Get one at: [bold underline]https://openrouter.ai/keys[/]",
            title="First-Run Setup",
            border_style="cyan",
        )
    )
    prompted_key = Prompt.ask("[bold green]Enter your OpenRouter API Key[/]", password=True)
    clean_key = prompted_key.strip() if prompted_key else ""
    if not is_valid_api_key(clean_key):
        console.print("[bold red]A valid API key is required to use Free Coding Agent. Exiting.[/]")
        raise typer.Exit(code=1)

    config_mgr.set_api_key(clean_key)
    console.print("[green]✓ API key saved to ~/.free-coding-agent/config.json.[/]\n")
    return clean_key


def handle_rate_limit(current_key: str, config_mgr: ConfigManager) -> str | None:
    """Prompt user for an alternative API key when daily limit or rate limit occurs."""
    console.print(
        Panel(
            "[bold yellow]OpenRouter Rate or Daily Quota Limit Reached![/]\n\n"
            "The current API key has exhausted its allocation or is rate-limited.\n"
            "Enter an alternative OpenRouter key to continue immediately, or press Enter to stop.",
            title="Quota Limit Reached",
            border_style="yellow",
        )
    )
    new_key = Prompt.ask("[bold yellow]Alternative OpenRouter API Key[/]", password=True)
    if new_key:
        clean_key = new_key.strip()
        if is_valid_api_key(clean_key):
            config_mgr.set_api_key(clean_key)
            console.print("[green]✓ Switched to new key and updated global config. Resuming turn...[/]\n")
            return clean_key
        else:
            console.print("[yellow]Invalid API key entered (control characters or too short). Key not saved.[/]\n")
    return None


def handle_key_update(config_mgr: ConfigManager, direct_key: str | None = None) -> str | None:
    """View or update the active OpenRouter API key via slash command."""
    current_key = config_mgr.get_api_key()

    if direct_key:
        candidate_key = direct_key.strip()
    else:
        if current_key:
            masked = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
            console.print(f"Active API Key: [bold cyan]{masked}[/]")
        else:
            console.print("[yellow]No valid API key currently configured.[/]")

        entered = Prompt.ask(
            "[bold green]Enter new OpenRouter API Key (or press Enter to cancel)[/]",
            password=True,
        )
        if not entered or not entered.strip():
            console.print("[dim]Key update cancelled. Active key unchanged.[/]\n")
            return current_key
        candidate_key = entered.strip()

    if not is_valid_api_key(candidate_key):
        console.print("[bold red]Invalid API key format (must be printable text, min 8 chars). Key not updated.[/]\n")
        return current_key

    config_mgr.set_api_key(candidate_key)
    masked_new = candidate_key[:8] + "..." + candidate_key[-4:] if len(candidate_key) > 12 else "***"
    console.print(f"[bold green]✓ API key updated successfully:[/] [cyan]{masked_new}[/]\n")
    return candidate_key


def execute_agent_task(
    task: str,
    project_root: Path,
    auto_approve: bool = False,
    session_id: str | None = None,
    initial_messages: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    quiet_header: bool = False,
) -> None:
    """Run the agent loop on a single user prompt."""
    config_mgr = ConfigManager()
    api_key = resolve_api_key(config_mgr)
    status_manager = StatusManager(console)

    def rate_limit_cb(curr: str) -> str | None:
        was_active = status_manager.is_active()
        if was_active:
            status_manager.stop()
        try:
            return handle_rate_limit(curr, config_mgr)
        finally:
            if was_active:
                status_manager.update("Thinking...")

    provider = OpenRouterProvider(
        api_key=api_key,
        model=model,
        on_fallback=handle_fallback,
        on_rate_limit=rate_limit_cb,
    )
    registry = get_default_registry()
    confirm_cb = make_confirmation_callback(auto_approve)
    sm = SessionManager(project_root)
    active_session_id = session_id or sm.generate_session_id()

    loop = AgentLoop(
        provider=provider,
        project_root=project_root,
        tools=registry,
        on_step=render_step,
        on_status=status_manager.update,
        confirmation_callback=confirm_cb,
        session_manager=sm,
        session_id=active_session_id,
        initial_messages=initial_messages,
    )

    if not quiet_header:
        console.print(f"[bold blue]Workspace Root:[/] {project_root}")
        console.print(f"[bold cyan]Session ID:[/]     {active_session_id}")
        console.print(f"[bold magenta]Model Target:[/]   {model}")
        console.print(f"[bold blue]Task:[/]           {task}\n")

    try:
        loop.run(task)
    except Exception as err:
        console.print(
            Panel(
                f"[bold red]Execution failed:[/]\n{err}",
                title="Agent Error",
                border_style="red",
            )
        )
        if not quiet_header:
            raise typer.Exit(code=1) from err
    finally:
        status_manager.stop()


def display_welcome_banner(workspace: Path, model: str, session_id: str) -> None:
    """Render a clean welcome banner with workspace and session info."""
    welcome_text = (
        f"[bold white]Free Coding Agent[/] [dim]({model})[/]\n"
        f"[dim]Workspace:[/] [blue]{workspace}[/]\n"
        f"[dim]Session:[/]   [cyan]{session_id}[/]\n\n"
        f"Type your task or instruction to begin.\n"
        f"Commands: [cyan]/new-chat[/], [cyan]/key[/], [cyan]/history[/], [cyan]/model[/], [cyan]/clear[/], [cyan]/help[/], [cyan]/exit[/]"
    )
    console.print(Panel(welcome_text, border_style="bright_blue", padding=(1, 2)))


def display_slash_help() -> None:
    """Display table of available interactive slash commands."""
    table = Table(title="Interactive Slash Commands", border_style="cyan")
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_row("/new-chat, /new", "Start a brand new conversation with clean context")
    table.add_row("/key, /api-key", "View or update your OpenRouter API key")
    table.add_row("/history, /sessions", "List past conversation sessions and resume one")
    table.add_row("/model", "View or change the active LLM identifier")
    table.add_row("/clear", "Clear terminal screen while keeping conversation context")
    table.add_row("/help", "Show this list of commands")
    table.add_row("/exit, /quit", "Exit Free Coding Agent")
    console.print(table)


def prompt_select_history(sm: SessionManager) -> tuple[str, list[dict]] | None:
    """Display session history table and prompt user to select a session to resume."""
    all_sessions = sm.list_sessions()
    if not all_sessions:
        console.print("[yellow]No saved sessions found for this workspace.[/]")
        return None

    table = Table(title="Chat Session History", border_style="blue")
    table.add_column("#", style="bold yellow", justify="right", width=3)
    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Last Active", style="dim")
    table.add_column("Msgs", justify="right")
    table.add_column("Topic / First Task", style="green")

    for idx, s in enumerate(all_sessions, start=1):
        task_preview = s["task"][:50] + ("..." if len(s["task"]) > 50 else "")
        table.add_row(
            str(idx),
            s["session_id"],
            s["updated_at"][:19].replace("T", " "),
            str(s["message_count"]),
            task_preview,
        )
    console.print(table)

    choice = Prompt.ask(
        "\n[bold green]Enter session # or ID to resume (or press Enter to cancel)[/]",
        default="",
    ).strip()

    if not choice:
        return None

    target_id: str | None = None
    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(all_sessions):
            target_id = all_sessions[index]["session_id"]
        else:
            console.print(f"[red]Invalid selection number: {choice}[/]")
            return None
    else:
        target_id = choice

    loaded = sm.load_session(target_id)
    if not loaded:
        console.print(f"[red]Session '{target_id}' not found.[/]")
        return None

    console.print(
        f"[green]✓ Resumed session:[/] [cyan]{loaded.session_id}[/] "
        f"[dim]({len(loaded.messages)} messages, Topic: '{loaded.task}')[/]"
    )
    return loaded.session_id, loaded.messages


def handle_model_switch(current_model: str) -> str:
    """Prompt user to view or change the active model."""
    console.print(f"Current model: [bold cyan]{current_model}[/]")
    new_model = Prompt.ask(
        "[bold green]Enter new model identifier (or press Enter to keep current)[/]",
        default="",
    ).strip()
    if new_model:
        console.print(f"[green]✓ Switched model to:[/] [bold cyan]{new_model}[/]")
        return new_model
    return current_model


SLASH_COMMAND_SUGGESTIONS: list[tuple[str, str]] = [
    ("/new-chat", "Start a brand new conversation with fresh context"),
    ("/key", "View or update your OpenRouter API key"),
    ("/api-key", "View or update your OpenRouter API key"),
    ("/history", "View and resume previous chat sessions"),
    ("/model", "View or change the active LLM identifier"),
    ("/clear", "Clear terminal screen while keeping context"),
    ("/help", "Show table of available commands"),
    ("/exit", "Exit Free Coding Agent"),
]


class SlashCommandCompleter(Completer):
    """Provides autocomplete suggestions for slash commands when typing '/'."""

    def __init__(self, commands: list[tuple[str, str]] | None = None) -> None:
        self.commands = commands or SLASH_COMMAND_SUGGESTIONS

    def get_completions(self, document: Document, complete_event: Any):
        text = document.text_before_cursor
        # Only suggest when typing a slash command without arguments
        if text.startswith("/") and " " not in text:
            word = text.lower()
            for cmd, desc in self.commands:
                if cmd.startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc,
                    )


def create_prompt_session() -> PromptSession | None:
    """Create a PromptSession with slash command autocompletion and arrow navigation."""
    if not sys.stdin.isatty():
        return None

    kb = KeyBindings()

    # Arrow keys navigate completion menu when popup is visible
    @kb.add("down", filter=has_completions)
    def _select_next(event):
        event.current_buffer.complete_next()

    @kb.add("up", filter=has_completions)
    def _select_prev(event):
        event.current_buffer.complete_previous()

    # Enter key applies selected suggestion and executes
    @kb.add("enter", filter=completion_is_selected)
    def _apply_and_execute(event):
        buf = event.current_buffer
        buf.apply_completion(buf.complete_state.current_completion)
        buf.validate_and_handle()

    style = Style.from_dict({
        "prompt": "bold #00d7ff",
        "completion-menu.completion": "bg:#20222b #e0e0e0",
        "completion-menu.completion.current": "bg:#00d7ff #000000 bold",
        "completion-menu.meta.completion": "bg:#16171e #8a8f98",
        "completion-menu.meta.completion.current": "bg:#00b8e6 #000000 italic",
        "scrollbar.background": "bg:#16171e",
        "scrollbar.button": "bg:#3a3d4d",
    })

    completer = SlashCommandCompleter()
    history = InMemoryHistory()

    try:
        return PromptSession(
            completer=completer,
            complete_while_typing=True,
            key_bindings=kb,
            style=style,
            history=history,
        )
    except Exception:
        try:
            from prompt_toolkit.output.vt100 import Vt100_Output
            out = Vt100_Output(sys.stdout, lambda: (80, 24))
            return PromptSession(
                completer=completer,
                complete_while_typing=True,
                key_bindings=kb,
                style=style,
                history=history,
                output=out,
            )
        except Exception:
            return None


def run_interactive_session(
    workspace: Path,
    auto_approve: bool = False,
    initial_model: str = DEFAULT_MODEL,
    resume_session_id: str | None = None,
) -> None:
    """Launch full interactive conversational coding session."""
    config_mgr = ConfigManager()
    resolve_api_key(config_mgr)
    sm = SessionManager(workspace)

    current_model = initial_model
    current_session_id = resume_session_id or sm.generate_session_id()
    messages: list[dict] | None = None

    if resume_session_id:
        loaded = sm.load_session(resume_session_id)
        if loaded:
            messages = loaded.messages
            console.print(f"[green]✓ Resumed session:[/] [cyan]{loaded.session_id}[/]")
        else:
            console.print(f"[yellow]Session '{resume_session_id}' not found. Starting fresh session.[/]")

    display_welcome_banner(workspace, current_model, current_session_id)
    prompt_session = create_prompt_session()

    while True:
        try:
            if prompt_session is not None:
                user_input = prompt_session.prompt([("class:prompt", "\nagent> ")]).strip()
            else:
                user_input = Prompt.ask("\n[bold cyan]agent>[/]").strip()
            if not user_input:
                continue

            # Process slash commands
            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else None

                if cmd in ("/exit", "/quit"):
                    console.print("[dim]Goodbye![/]")
                    break
                elif cmd in ("/help", "/?"):
                    display_slash_help()
                    continue
                elif cmd in ("/new", "/new-chat"):
                    current_session_id = sm.generate_session_id()
                    messages = None
                    console.print(f"[bold green]✓ Started new chat session:[/] [cyan]{current_session_id}[/]")
                    continue
                elif cmd in ("/key", "/api-key", "/apikey", "/set-key"):
                    handle_key_update(config_mgr, direct_key=arg)
                    continue
                elif cmd in ("/history", "/sessions"):
                    history_res = prompt_select_history(sm)
                    if history_res:
                        current_session_id, messages = history_res
                    continue
                elif cmd == "/clear":
                    console.clear()
                    display_welcome_banner(workspace, current_model, current_session_id)
                    continue
                elif cmd == "/model":
                    current_model = handle_model_switch(current_model)
                    continue
                else:
                    console.print(f"[yellow]Unknown command '{user_input}'. Type [bold]/help[/] for commands.[/]")
                    continue

            # Check for plain exit keywords
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/]")
                break

            # Execute conversational turn
            execute_agent_task(
                task=user_input,
                project_root=workspace,
                auto_approve=auto_approve,
                session_id=current_session_id,
                initial_messages=messages,
                model=current_model,
                quiet_header=True,
            )

            # Reload updated messages for subsequent conversational turns
            reloaded = sm.load_session(current_session_id)
            if reloaded:
                messages = reloaded.messages

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit or enter a new query.[/]")
            continue
        except EOFError:
            console.print("\n[dim]Goodbye![/]")
            break


@app.command()
def main(
    task: Annotated[
        Optional[str],
        typer.Argument(
            help="Task instruction for the coding agent. If omitted, launches interactive chat session."
        ),
    ] = None,
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            help="Directory to use as workspace project root.",
        ),
    ] = Path.cwd(),
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically approve file edits, writes, and shell execution without confirmation.",
        ),
    ] = False,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model identifier on OpenRouter (default: 'openrouter/free').",
        ),
    ] = DEFAULT_MODEL,
    resume: Annotated[
        Optional[str],
        typer.Option(
            "--resume",
            "-r",
            help="Resume an existing session by its session ID.",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            "-s",
            help="List all saved sessions and exit.",
        ),
    ] = False,
) -> None:
    """Autonomous CLI Coding Agent powered by OpenRouter."""
    sm = SessionManager(workspace)

    # Handle --sessions flag
    if sessions:
        all_sessions = sm.list_sessions()
        if not all_sessions:
            console.print("[yellow]No saved sessions found for this workspace.[/]")
            return

        table = Table(title="Saved Agent Sessions", border_style="blue")
        table.add_column("Session ID", style="cyan", no_wrap=True)
        table.add_column("Last Updated", style="dim")
        table.add_column("Messages", justify="right")
        table.add_column("Original Task", style="green")

        for s in all_sessions:
            table.add_row(
                s["session_id"],
                s["updated_at"][:19].replace("T", " "),
                str(s["message_count"]),
                s["task"][:60] + ("..." if len(s["task"]) > 60 else ""),
            )
        console.print(table)
        return

    # Single-task CLI execution
    if task:
        initial_messages = None
        if resume:
            loaded = sm.load_session(resume)
            if not loaded:
                console.print(f"[bold red]Session '{resume}' not found in {sm.storage_dir}[/]")
                raise typer.Exit(code=1)
            initial_messages = loaded.messages
            console.print(f"[bold green]Resuming Session:[/] {loaded.session_id} (Prior task: '{loaded.task}')")

        execute_agent_task(
            task,
            workspace,
            auto_approve=yes,
            session_id=resume,
            initial_messages=initial_messages,
            model=model,
        )
        return

    # Interactive conversational flow (Antigravity-style)
    run_interactive_session(
        workspace=workspace,
        auto_approve=yes,
        initial_model=model,
        resume_session_id=resume,
    )


if __name__ == "__main__":
    app()
