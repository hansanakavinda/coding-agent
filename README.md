# CLI Coding Agent (OpenRouter Free Tier)

An autonomous, framework-free CLI coding agent built from scratch in Python. It interfaces directly with OpenRouter's free-tier LLMs via OpenAI-compatible endpoints, orchestrating a local agentic loop to inspect, reason about, and modify code in your project workspace.

---

## Key Architecture Principles

1. **Framework-Free by Design**: No LangChain, LlamaIndex, or AutoGen. The agentic loop, tool dispatch system, message history, and context management are crafted from scratch to provide deep mechanical visibility.
2. **Resilient Free-Tier Routing**: Automatically attempts candidate free models in sequence, gracefully falling back if upstream rate limits (HTTP 429) or transient server issues occur.
3. **Strict Path Jailing**: Every tool execution is strictly sandboxed to the project directory boundary. Traversal attempts (e.g. `../../`) or external absolute paths are rejected with a loud `PathJailError`.
4. **Rich Terminal UX**: Powered by `rich` and `typer`, presenting formatted panels for model thoughts, tool calls, tool results, and the active serving model.

---

## Project Structure

```
coding-agent/
├── core/
│   ├── __init__.py
│   ├── types.py            # Typed dataclasses: ToolCall, ToolResult, ProviderResponse, AgentStep, AgentResult
│   └── loop.py             # Framework-free agentic loop (turns, dispatch, termination)
├── tools/
│   ├── __init__.py         # Tool registry, schema generation, and dynamic execution dispatch
│   ├── base.py             # BaseTool abstract class & safe_resolve_path security jail
│   └── read_file.py        # 1-based line-numbered file reader with error handling
├── providers/
│   ├── __init__.py
│   ├── base.py             # LLMProvider abstract interface
│   └── openrouter.py       # OpenRouter client with candidate fallback chain
├── memory/
│   └── __init__.py         # Context budget and session persistence (scaffolded)
├── tests/
│   ├── test_path_jail.py   # Boundary security and directory traversal tests
│   ├── test_read_file.py   # Line numbering and edge-case reading tests
│   └── test_loop.py        # Deterministic multi-turn agent loop test
├── cli.py                  # Typer & Rich command-line entrypoint (single task & REPL)
├── pyproject.toml          # Package metadata and CLI console script
├── .env.example            # Environment configuration template
└── README.md               # Documentation and guide
```

---

## Setup & Installation

### 1. Requirements
- Python 3.11+
- An [OpenRouter](https://openrouter.ai/) account (free key)

### 2. Configure Environment
Create a `.env` file from the example:
```bash
cp .env.example .env
```
Add your OpenRouter API key inside `.env`:
```env
OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. Install Dependencies
```bash
pip install -e .
```
Or install required packages manually:
```bash
pip install typer rich httpx python-dotenv pytest
```

---

## Usage

### Single-Task Execution
```bash
python cli.py "Inspect pyproject.toml and summarize the project dependencies."
```

### Interactive REPL Mode
Run `cli.py` without arguments to open an interactive session:
```bash
python cli.py
```
Inside the REPL, type your instructions or `exit` / `quit` to end.

---

## Running Tests

Run the complete test suite with `pytest`:
```bash
pytest -v
```

---

## Implementation Milestones

- [x] **Milestone 1: Repository Scaffolding & Bare Agentic Loop**
  - Framework-free loop with typed message history
  - `read_file` tool with line numbers
  - Path jailing boundary security (`safe_resolve_path`)
  - OpenRouter client with multi-model fallback chain
  - Deterministic test suite with 100% pass rate
- [ ] **Milestone 2: Model Provider Layer Refinements**
- [ ] **Milestone 3: ReAct Prompted Tool-Calling Fallback**
- [ ] **Milestone 4: Core Tool Set (`list_directory`, `grep`, `edit_file`, `write_file`, `run_bash`)**
- [ ] **Milestone 5: Context Management & Truncation Budget**
- [ ] **Milestone 6: Session Persistence & Resumption**
- [ ] **Milestone 7: CLI UX Polish & Diffs**
