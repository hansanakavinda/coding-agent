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
from rich.prompt import Prompt
import typer

from core.loop import AgentLoop
from core.types import AgentStep
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


def execute_agent_task(task: str, project_root: Path) -> None:
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

    loop = AgentLoop(
        provider=provider,
        project_root=project_root,
        tools=registry,
        on_step=render_step,
    )

    console.print(f"[bold blue]Workspace Root:[/] {project_root}")
    console.print(f"[bold blue]Task:[/] {task}\n")

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
) -> None:
    """Autonomous CLI Coding Agent powered by OpenRouter."""
    if task:
        execute_agent_task(task, workspace)
        return

    # Interactive REPL mode
    console.print(
        Panel(
            "[bold green]Coding Agent REPL[/]\n"
            "Type your instruction or prompt. Type [bold red]exit[/] or [bold red]quit[/] to leave.",
            border_style="blue",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]agent[/]")
            if not user_input or user_input.strip() == "":
                continue
            if user_input.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/]")
                break
            execute_agent_task(user_input.strip(), workspace)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Interrupted. Exiting REPL...[/]")
            break


if __name__ == "__main__":
    app()
