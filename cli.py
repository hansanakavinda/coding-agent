"""Command-line interface for the coding agent."""

import os
from pathlib import Path
import sys
from typing import Annotated, Optional

# Ensure standard output streams support UTF-8 on Windows
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
import typer

from core.loop import AgentLoop
from core.types import AgentStep, ConfirmationCallback
from memory.session import SessionManager
from providers.openrouter import DEFAULT_CANDIDATE_MODELS, OpenRouterProvider
from tools import get_default_registry

# Automatically search and load .env from current directory or parent directories
load_dotenv()

app = typer.Typer(
    help="Autonomous CLI Coding Agent built from scratch for OpenRouter free models.",
    add_completion=False,
)
console = Console(highlight=False)


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


def make_confirmation_callback(auto_approve: bool) -> ConfirmationCallback | None:
    """Create user confirmation prompt handler unless auto-approve is active."""
    if auto_approve:
        return None

    def confirm(action: str, details: str) -> bool:
        if action == "edit_file":
            title = "[yellow]Confirm File Edit (Unified Diff)[/]"
            border_style = "yellow"
        elif action == "write_file":
            title = "[yellow]Confirm File Write (Preview)[/]"
            border_style = "yellow"
        elif action == "run_bash":
            title = "[red]Confirm Shell Execution[/]"
            border_style = "red"
        else:
            title = f"[yellow]Confirm Action: {action}[/]"
            border_style = "yellow"

        console.print(Panel(details, title=title, border_style=border_style))
        return Confirm.ask(
            f"[bold]Approve execution of [cyan]{action}[/]?[/]",
            default=True,
        )

    return confirm


def execute_agent_task(
    task: str,
    project_root: Path,
    auto_approve: bool = False,
    session_id: str | None = None,
    initial_messages: list[dict] | None = None,
) -> None:
    """Run the agent loop on a single user prompt."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print(
            Panel(
                "[bold red]OPENROUTER_API_KEY not found![/]\n\n"
                "Please set it in your environment or in a [bold].env[/] file:\n"
                "OPENROUTER_API_KEY=your_key_here",
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    provider = OpenRouterProvider(
        api_key=api_key,
        candidate_models=DEFAULT_CANDIDATE_MODELS,
        on_fallback=handle_fallback,
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
        confirmation_callback=confirm_cb,
        session_manager=sm,
        session_id=active_session_id,
        initial_messages=initial_messages,
    )

    console.print(f"[bold blue]Workspace Root:[/] {project_root}")
    console.print(f"[bold cyan]Session ID:[/]     {active_session_id}")
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
        raise typer.Exit(code=1) from err


@app.command()
def main(
    task: Annotated[
        Optional[str],
        typer.Argument(
            help="Task instruction for the coding agent. If omitted, launches interactive REPL."
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
            console.print("[yellow]No saved sessions found in workspace.[/]")
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

    # Handle --resume flag
    initial_messages = None
    if resume:
        loaded = sm.load_session(resume)
        if not loaded:
            console.print(f"[bold red]Session '{resume}' not found in {sm.storage_dir}[/]")
            raise typer.Exit(code=1)
        initial_messages = loaded.messages
        console.print(f"[bold green]Resuming Session:[/] {loaded.session_id} (Prior task: '{loaded.task}')")

    if task:
        execute_agent_task(
            task,
            workspace,
            auto_approve=yes,
            session_id=resume,
            initial_messages=initial_messages,
        )
        return

    # Interactive REPL mode
    console.print(
        Panel(
            "[bold green]Coding Agent REPL[/]\n"
            "Type your instruction or prompt. Type [bold red]exit[/] or [bold red]quit[/] to leave.",
            border_style="blue",
        )
    )

    current_session_id = resume or sm.generate_session_id()
    while True:
        try:
            user_input = Prompt.ask(f"\n[bold cyan]agent [{current_session_id}][/]")
            if not user_input or user_input.strip() == "":
                continue
            if user_input.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/]")
                break
            execute_agent_task(
                user_input.strip(),
                workspace,
                auto_approve=yes,
                session_id=current_session_id,
                initial_messages=initial_messages,
            )
            # Subsequent REPL turns reload the updated messages
            reloaded = sm.load_session(current_session_id)
            if reloaded:
                initial_messages = reloaded.messages
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Interrupted. Exiting REPL...[/]")
            break


if __name__ == "__main__":
    app()
