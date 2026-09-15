# CLI Coding Agent (OpenRouter Free Tier)

An autonomous, framework-free CLI coding agent built from scratch in Python. It interfaces directly with OpenRouter's free-tier LLMs via OpenAI-compatible endpoints, orchestrating a local agentic loop to inspect, reason about, and modify code in your project workspace.

---

## Key Architecture Principles

1. **Framework-Free by Design**: No LangChain, LlamaIndex, or AutoGen. The agentic loop, tool dispatch system, message history, and context management are crafted from scratch to provide deep mechanical visibility.
2. **Resilient Free-Tier Routing**: Automatically attempts candidate free models in sequence, gracefully falling back if upstream rate limits (HTTP 429) or transient server issues occur.
3. **ReAct Prompted Fallback with Retry**: Seamlessly supports models without native tool calling via structured ```json fenced blocks, strict schema validation, and automatic single-retry prompting on malformed outputs.
4. **Strict Path Jailing**: Every tool execution is strictly sandboxed to the project directory boundary. Traversal attempts (e.g. `../../`) or external absolute paths are rejected with a loud `PathJailError`.
5. **Exact Match File Editing**: `edit_file` enforces that the target string (`old_str`) matches exactly once in the file to avoid accidental or ambiguous modifications.
6. **Safety & Confirmation Modals**: File writes, targeted string replacements, and shell commands require explicit user confirmation with interactive syntax-highlighted diffs or command previews unless run with `--yes` / `-y`.
7. **Rich Terminal UX**: Powered by `rich` and `typer`, presenting formatted panels for model thoughts, tool calls, tool results, and the active serving model.

---

## Project Structure

```
coding agent/
├── core/
│   ├── __init__.py
│   ├── types.py            # Typed dataclasses: ToolCall, ToolResult, ProviderResponse, AgentStep, AgentResult
│   ├── fallback_parser.py  # ReAct prompted fallback instructions, JSON block parser, and validator
│   └── loop.py             # Framework-free agentic loop (turns, dispatch, retries, termination)
├── tools/
│   ├── __init__.py         # Tool registry, schema generation, and dynamic execution dispatch
│   ├── base.py             # BaseTool abstract class, diff generator, and safe_resolve_path security jail
│   ├── read_file.py        # 1-based line-numbered file reader
│   ├── list_directory.py   # Workspace directory lister with human-readable file sizes
│   ├── grep.py             # Regex & text pattern searcher skipping noise folders
│   ├── edit_file.py        # Exact-match targeted string replacement with unified diff
│   ├── write_file.py       # File creator/overwriter with confirmation preview
│   └── run_bash.py         # Shell command executor with timeout and status code preservation
├── providers/
│   ├── __init__.py
│   ├── base.py             # LLMProvider abstract interface
│   └── openrouter.py       # OpenRouter client with candidate fallback chain & prompted retry
├── memory/
│   └── __init__.py         # Context budget and session persistence (scaffolded)
├── tests/
│   ├── test_path_jail.py   # Boundary security and directory traversal tests
│   ├── test_read_file.py   # Line numbering and edge-case reading tests
│   ├── test_list_directory.py # Directory listing & git exclusion tests
│   ├── test_grep.py        # Regex & literal file search tests
│   ├── test_edit_file.py   # Exact-match single occurrence & diff confirmation tests
│   ├── test_write_file.py  # File creation, overwrite, and confirmation tests
│   ├── test_run_bash.py    # Shell execution, timeout, and status code tests
│   ├── test_fallback_parser.py # Fenced JSON parsing & malformed syntax tests
│   ├── test_prompted_loop.py   # Prompted fallback & retry-on-malformed-output tests
│   └── test_loop.py        # Deterministic multi-turn agent loop test
├── cli.py                  # Typer & Rich command-line entrypoint (single task & REPL)
├── agent.py                # Convenient root entrypoint wrapper pointing to cli.py
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
python agent.py "Inspect pyproject.toml and summarize the project dependencies."
```

### Resuming Previous Sessions
List all saved sessions in the current workspace:
```bash
python agent.py --sessions
```

Resume an existing session to continue context across CLI commands:
```bash
python agent.py --resume <session_id> "Now create unit tests for the functions you just inspected"
```

### Auto-Approve Edits & Commands
By default, `edit_file`, `write_file`, and `run_bash` prompt for confirmation. Pass `--yes` or `-y` to auto-approve:
```bash
python agent.py --yes "Run pytest and summarize any test failures"
```

### Interactive REPL Mode
Run `agent.py` or `cli.py` without arguments to launch an interactive REPL session:
```bash
python agent.py
```
Inside the REPL, type your instructions or `exit` / `quit` to leave.

---

## Running Tests

Run the complete test suite with `pytest`:
```bash
pytest -v
```
All 46 unit tests run deterministically with mocked responses and isolated temporary directories.

---

## Implementation Milestones

- [x] **Milestone 1: Repository Scaffolding & Bare Agentic Loop**
  - Framework-free loop with typed message history
  - `read_file` tool with line numbers
  - Path jailing boundary security (`safe_resolve_path`)
  - OpenRouter client with multi-model fallback chain
- [x] **Milestone 2: Model Provider Layer Refinements**
  - Candidate model chain: `nvidia/nemotron-3-super-120b-a12b:free` -> `google/gemma-4-31b-it:free` -> `openrouter/free`
  - Automatic detection and recovery from upstream HTTP 429 rate limits
  - Logging of actual serving model in console output
- [x] **Milestone 3: ReAct Prompted Tool-Calling Fallback**
  - Fenced structured ```json block parsing
  - Strict validator for `tool` and `args` schemas
  - Retry-on-malformed-output with dynamic re-prompting
- [x] **Milestone 4: Core Tool Set**
  - `read_file(path)`
  - `list_directory(path)`
  - `grep(pattern, path)`
  - `edit_file(path, old_str, new_str)` (exact-match, fails loudly on duplicates or missing)
  - `write_file(path, content)`
  - `run_bash(command)` (with timeout and exit code preservation)
  - Interactive user confirmation diffs / previews & `--yes` flag
- [x] **Milestone 5: Context Management & Truncation Budget**
  - Accurate token counting via `tiktoken` with fallback heuristic
  - Tool output truncation preserving head and tail with omission notices
  - Atomic conversation pruning keeping system prompt and recent turns intact
- [x] **Milestone 6: Session Persistence & Resumption**
  - Automatic session checkpoints stored in `.agent_sessions/*.json`
  - Session listing (`agent --sessions`)
  - Seamless resumption across crashes or closed terminals (`agent --resume <session_id>`)
- [x] **Milestone 7: CLI UX Polish & Diffs**
  - Rich colored panels for tool invocations, results, thoughts, and answers
  - Unified syntax diffs and preview modals for confirmations
  - Real-time terminal output with UTF-8 encoding support on Windows
