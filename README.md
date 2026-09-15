# Free Coding Agent (`free-coding-agent`)

An autonomous, framework-free CLI coding agent powered by OpenRouter's free-tier models. Designed to be installed globally and run inside any project repository without polluting the codebase with sessions or configuration files.

---

## Highlights

1. **Zero Workspace Pollution**: Under no circumstances are sessions, history logs, or `.env` files written to your target workspace. All state is strictly centralized in `~/.free-coding-agent/`.
2. **First-Class Free-Tier Support**: Preconfigured for the `openrouter/free` meta-router, routing automatically to top active free coding models with candidate fallback chains.
3. **Interactive Setup & Daily Quota Recovery**:
   - Prompts for your OpenRouter key with masked input on first run and saves it globally.
   - Gracefully detects HTTP 429 rate limits or exhausted daily free quotas, prompting dynamically for an alternative free key so you never lose conversational context mid-task.
4. **Framework-Free by Design**: Built from scratch without LangChain, LlamaIndex, or AutoGen. Every part of the agentic loop, tool dispatch, and prompt engineering is clean, readable, and fully auditable.
5. **ReAct Prompted Fallback with Retry**: Works across models with or without native tool-calling capabilities using structured JSON blocks, validation schemas, and self-healing single-retry prompts.
6. **Strict Path Jailing**: Every file read, write, edit, and search is sandboxed to the active workspace. Traversal attempts (e.g. `../../`) are blocked with a clear `PathJailError`.
7. **Interactive Safety Modals**: Displays syntax-highlighted unified diffs before modifying files and previews shell commands before execution (pass `--yes` / `-y` to auto-approve).
8. **Rich Terminal UX**: Formatted terminal output powered by `rich` and `typer`, detailing model thoughts, tool calls, execution outputs, and final responses.

---

## Project Structure

```
coding agent/
├── core/
│   ├── __init__.py
│   ├── types.py            # Dataclasses: ToolCall, ToolResult, ProviderResponse, AgentStep, AgentResult
│   ├── fallback_parser.py  # ReAct fallback instructions, JSON block parser, and validator
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
│   └── openrouter.py       # OpenRouter client with fallback chain, prompted retry, and rate-limit recovery
├── memory/
│   ├── __init__.py         # Module exports
│   ├── config.py           # Centralized configuration manager (~/.free-coding-agent/config.json)
│   ├── session.py          # Centralized session persistence (~/.free-coding-agent/sessions/)
│   └── context.py          # Token budgeting, tool output truncation, and conversation pruning
├── tests/
│   ├── test_config.py      # Global config management and environment variable precedence tests
│   ├── test_session.py     # Centralized session isolation and zero-pollution tests
│   ├── test_context.py     # Token estimation, truncation, and atomic pruning tests
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
├── cli.py                  # Typer & Rich CLI entrypoint with single-task and REPL modes
├── agent.py                # Wrapper entrypoint pointing to cli.py
├── pyproject.toml          # Package metadata and console scripts (free-agent, free-coding-agent)
└── README.md               # Documentation and usage guide
```

---

## Installation

### Option 1: Global Install via `pipx` (Recommended)

[`pipx`](https://pypa.github.io/pipx/) installs the CLI in an isolated environment while exposing the binary globally across your system:

```bash
# From the repository root
pipx install .

# Or directly from GitHub (once published)
pipx install git+https://github.com/your-username/free-coding-agent.git
```

Now you can invoke `free-agent` or `free-coding-agent` from any terminal or directory on your system.

### Option 2: Standard Python Virtual Environment

```bash
# Clone the repository
git clone https://github.com/your-username/free-coding-agent.git
cd free-coding-agent

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install in editable mode
pip install -e .
```

---

## Configuration & API Keys

Free Coding Agent uses OpenRouter to access free models. You do **not** need to manually create `.env` files in your projects.

### Automatic First-Run Setup
Simply run `free-agent`. If no key is found, the CLI will display a welcome panel and prompt for your OpenRouter key with secure masked input:
```
╭─ First-Run Setup ──────────────────────────────────────────╮
│ Welcome to Free Coding Agent!                              │
│                                                            │
│ To get started, you need an OpenRouter API key.            │
│ Get one at: https://openrouter.ai/keys                     │
╰────────────────────────────────────────────────────────────╯
Enter your OpenRouter API Key: ••••••••••••••••••••••••
✓ API key saved to ~/.free-coding-agent/config.json.
```

### Dynamic Quota Limit Recovery
Free-tier keys are subject to daily request limits. If your active key hits a quota limit (HTTP 429), Free Coding Agent catches it gracefully:
```
╭─ Quota Limit Reached ──────────────────────────────────────╮
│ OpenRouter Rate or Daily Quota Limit Reached!              │
│ Enter an alternative OpenRouter key to continue            │
│ immediately, or press Enter to stop.                       │
╰────────────────────────────────────────────────────────────╯
Alternative OpenRouter API Key: ••••••••••••••••••••••••
✓ Switched to new key and updated global config. Resuming turn...
```

### Alternative Configuration Methods
You can also provide your API key via:
- **Environment Variable**: `export OPENROUTER_API_KEY="sk-or-v1-..."` (or `$env:OPENROUTER_API_KEY="..."` on PowerShell)
- **Config File**: Edit `~/.free-coding-agent/config.json` manually:
  ```json
  {
    "openrouter_api_key": "sk-or-v1-...",
    "default_model": "openrouter/free"
  }
  ```

---

## Usage Guide

You can run Free Coding Agent using any of the installed commands: `free-agent`, `free-coding-agent`, or `agent`.

### 1. Interactive Conversational Mode (Default)
Simply run `agent` or `free-agent` from any directory to start an interactive pair-programming session:
```bash
free-agent
```

Type your requests naturally and continue chatting. The agent preserves full context across turns.

#### Supported Slash Commands
Within the interactive prompt, type `/` to access commands:
| Command | Description |
| :--- | :--- |
| `/new-chat`, `/new` | Start a brand new conversation with fresh context |
| `/history`, `/sessions` | View past sessions for this workspace and select one to resume |
| `/model` | View or change the active LLM identifier |
| `/clear` | Clear terminal screen while preserving context |
| `/help` | Display table of available commands |
| `/exit`, `/quit` | Exit Free Coding Agent |

### 2. Single Task Execution
Execute a one-off task instruction directly from the command line:
```bash
free-agent "Inspect pyproject.toml and summarize the project dependencies."
```

Target a different workspace directory:
```bash
free-agent -w C:\path\to\another\project "Find all TODO comments and summarize them"
```

### 3. Auto-Approve Confirmations (`--yes` / `-y`)
By default, destructive actions (`edit_file`, `write_file`, and `run_bash`) prompt for interactive confirmation. Pass `-y` to bypass prompts in scripts or automated pipelines:
```bash
free-agent -y "Run pytest and fix any failing unit tests"
```

### 4. Session Persistence & Resumption
Sessions are stored centrally under `~/.free-coding-agent/sessions/` mapped to each workspace path hash:

List saved sessions from the CLI:
```bash
free-agent --sessions
```

Resume an existing session directly:
```bash
free-agent --resume <session_id>
```

---

## Running the Test Suite

Free Coding Agent includes a comprehensive test suite (57 unit tests) covering all tools, security path jailing, ReAct fallback parsing, context truncation, rate-limit recovery, centralized session persistence, and interactive slash commands:

```bash
pytest -v
```

All tests execute deterministically in isolated temporary directories using mocked OpenRouter API responses.

---

## Milestones Completed

- [x] **Milestone 1: Repository Scaffolding & Bare Agentic Loop**
- [x] **Milestone 2: Model Provider Layer Refinements (`openrouter/free`)**
- [x] **Milestone 3: ReAct Prompted Tool-Calling Fallback & Single-Retry**
- [x] **Milestone 4: Sandboxed Core Tools (`read_file`, `write_file`, `edit_file`, `list_dir`, `grep`, `run_bash`)**
- [x] **Milestone 5: Token Budgeting & Head/Tail Tool Truncation**
- [x] **Milestone 6: Centralized Zero-Pollution Session Persistence**
- [x] **Milestone 7: Rich Interactive UX, Unified Diffs & REPL**
- [x] **Milestone 8: Productization & Packaging (`pipx` / setuptools, `~/.free-coding-agent/config.json`, dynamic rate-limit prompts)**
- [x] **Milestone 9: Interactive Flow & Slash Commands (`/new-chat`, `/history`, `/model`, `/clear`, `/help`, `/exit`)**

