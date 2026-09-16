# Contributing to Free Coding Agent

Thank you for your interest in contributing to Free Coding Agent!

## Getting Started

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/hansanakavinda/coding-agent.git
   cd coding-agent
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install in Editable Mode with Development Dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

Before submitting a pull request, ensure all tests pass:

```bash
pytest -v
```

All tests run in isolated temporary environments with mocked providers.

## Architecture Guidelines

- **Zero Workspace Pollution**: Never store session or agent state files in the workspace directory. Centralize state in `~/.free-coding-agent/`.
- **Framework-Free**: Avoid heavyweight agent frameworks (e.g. LangChain, AutoGen). Maintain direct, auditable control over loops, prompts, and tool calls.
- **Path Jailing**: All file tools must validate target paths through `safe_resolve_path`.

## Submitting Pull Requests

1. Create a feature branch: `git checkout -b feat/your-feature-name`.
2. Commit your changes with clear, descriptive commit messages.
3. Push to your fork and submit a Pull Request to `main`.
