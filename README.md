# CCMAS Python CLI

Multi-Agent System Python CLI - Learning reference project.

## Project Overview

CCMAS (Multi-Agent System) Python CLI is a Python implementation of multi-agent system core logic.

**This project references Claude Code source code and replicates its multi-agent system core functionality.**

Compatible with OpenAI-format models (vLLM, Ollama, MiniMax, DeepSeek, etc.).

## Screenshot

![CCMAS Startup](docs/ccmas-startup.png)

### Core Features

- **MAS Workflow** - Five sub-agent modes (Fork, Named, In-process, Tmux, Remote)
- **AutoCompact** - Automatic conversation compression when context is too long
- **Token Budget** - Support +500k syntax for budget control, auto-continue execution
- **Memory System** - MEMORY.md index system, auto-manage user/project memory
- **Permission Bubble** - permission\_mode='bubble' permission delegation
- **Tool System** - Bash, Read, Write, Edit, Glob, Grep, Agent
- **Async Support** - Built on asyncio
- **Interactive CLI** - Modern command-line interface
- **Skill System** - Install and invoke skills via /skill-name
- **Tmux Teammate** - True multi-terminal parallel Agent
- **Hooks System** - PreTool/PostTool hook support
- **Error Recovery** - Auto-retry, checkpoint restore
- **OpenClaw Integration** - Support external task coordination via state.json

## Installation

```bash
pip install -e .
```

## Quick Start

### First Use

```bash
ccmas --setup
ccmas
```

### Basic Usage

```bash
ccmas
ccmas "Write a Fibonacci function"
ccmas "+500k Implement a web server"
ccmas --ollama --model llama3
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_KEY --model MiniMax-M2.7
```

## CLI Arguments

| Argument              | Description             |
| --------------------- | ----------------------- |
| --setup               | Run setup wizard        |
| --reset               | Reset configuration     |
| --workspace, -w       | Working directory       |
| --model, -m           | Model name              |
| --api-base, -b        | API endpoint            |
| --api-key, -k         | API key                 |
| --ollama              | Use Ollama backend      |
| --vllm                | Use vLLM backend        |
| --temperature, -t     | Sampling temperature    |
| --permission-mode, -p | Permission mode         |
| --continue            | Continue last session   |
| --load-session        | Load historical session |
| --no-memory           | Disable Memory          |
| --verbose, -v         | Verbose output          |
| --version             | Show version            |

## Skill Commands

```bash
# Install a skill from GitHub
ccmas skill install user/repo
ccmas skill install user/repo/skill-name
ccmas skill install https://github.com/user/repo/blob/main/skills/my-skill/SKILL.md

# Install from local path
ccmas skill install /path/to/local/skill

# List installed skills
ccmas skill list

# Show skill info
ccmas skill info <name>

# Update a skill
ccmas skill update <name>

# Uninstall a skill
ccmas skill uninstall <name>
```

Skills are installed to `~/.ccmas/skills/<skill-name>/SKILL.md`.

## Core Features

### AutoCompact

When conversation context approaches token limit, CCMAS will:

1. Call LLM to generate conversation summary
2. Keep recent messages and key context
3. Insert compression boundary marker
4. Continue conversation

### Token Budget

Add `+500k` (or `use 2M tokens`) before task description:

```bash
ccmas "+500k Refactor the entire user authentication module"
```

System will:

- Track token usage
- Send continue message before budget exhausted
- Detect diminishing returns and stop correctly

### Memory System

CCMAS provides persistent Memory system:

```
~/.ccmas/
├── memory/
│   └── MEMORY.md        # User-level memory index
├── project/
│   └── {hash}/
│       └── MEMORY.md    # Project-level memory index
└── sessions/            # Session history
```

**Saving Memory**: AI automatically saves important info to Memory files:

1. Write to `~/.ccmas/memory/xxx.md`
2. Update `MEMORY.md` index

**Memory Types**:

- `user` - User role, preferences, knowledge
- `feedback` - User feedback and guidance
- `project` - Project-specific info
- `reference` - External system references

### Skill System

Skills are reusable instruction sets compatible with Claude Code's skill format.

**SKILL.md Format**:

```yaml
---
name: code-review
description: Perform a comprehensive code review
when_to_use: When you need to review code changes
allowed-tools: [Read, Grep, Bash]
model: opus
effort: high
context: fork
---

# Code Review

## Instructions
1. Fetch the changes
2. Review for bugs
3. Check style
```

Use `/code-review` to invoke the skill.

### Tmux Teammate

True parallel Agent via tmux:

```python
from ccmas.teammate.tmux import TmuxWorker

worker = TmuxWorker(name="researcher")
await worker.start()
await worker.send_message("Research X technology")
result = await worker.recv_response()
```

### CLAUDE.md Multi-level Discovery

Create `CLAUDE.md` at any location in project directory tree:

```
project/
├── CLAUDE.md              # Project root level
├── src/
│   ├── CLAUDE.md          # src directory level
│   └── components/
│       └── CLAUDE.md      # components directory level
```

System loads all files from shallow to deep by depth.

## Permission Modes

| Mode              | Description                        |
| ----------------- | ---------------------------------- |
| default           | Standard permission handling       |
| acceptEdits       | Auto-accept edits                  |
| bypassPermissions | Skip permission check              |
| bubble            | Permission bubbles to parent agent |
| plan              | Plan mode                          |
| auto              | Auto mode                          |

## Project Structure

```
ccmas-python-cli/
├── src/ccmas/
│   ├── agent/              # Agent system
│   │   ├── run_agent.py    # Agent execution engine
│   │   ├── fork_subagent.py # Fork sub-agent
│   │   ├── definition.py   # Agent definition
│   │   ├── agent_tool.py   # Agent tool
│   │   └── builtin/        # Builtin agents
│   ├── cli/                # CLI entry
│   │   ├── main.py         # Main entry
│   │   ├── commands.py     # Command handling
│   │   ├── config.py       # Config management
│   │   └── ui.py           # UI interface
│   ├── context/            # Context isolation
│   │   ├── agent_context.py
│   │   ├── teammate_context.py
│   │   └── subagent_context.py
│   ├── coordinator/        # Coordinator mode
│   ├── hooks/              # Hooks system
│   │   ├── manager.py      # Hook manager
│   │   └── integration.py  # Hook integration
│   ├── llm/                # LLM clients
│   │   ├── client.py       # Generic client
│   │   ├── openai.py       # OpenAI compatible
│   │   ├── ollama.py       # Ollama
│   │   └── vllm.py         # vLLM
│   ├── memory/             # Memory system
│   │   ├── loader.py       # Memory loader
│   │   ├── state_manager.py # State recovery
│   │   ├── template.py     # Memory template
│   │   ├── session.py      # Session management
│   │   ├── summarizer.py   # Summary generation
│   │   └── types.py        # Type definitions
│   ├── permission/         # Permission system
│   │   ├── checker.py      # Permission check
│   │   ├── mode.py         # Permission mode
│   │   └── bubble.py       # Permission bubble
│   ├── prompt/             # System prompts
│   │   ├── system.py       # System prompt
│   │   ├── tools.py        # Tool prompts
│   │   └── agent.py        # Agent prompts
│   ├── query/              # Query loop
│   │   ├── loop.py         # Main loop
│   │   ├── compact.py      # Auto compact
│   │   ├── token_budget.py # Budget control
│   │   ├── summarizer.py   # Summarizer
│   │   ├── tool_executor.py # Tool executor
│   │   └── message_builder.py # Message builder
│   ├── skill/              # Skill system
│   │   ├── manager.py      # Skill manager
│   │   ├── tool.py        # Skill tool
│   │   └── commands.py     # Skill commands
│   ├── teammate/           # Teammate system
│   │   ├── tmux.py        # Tmux implementation
│   │   ├── in_process.py  # In-process
│   │   ├── mailbox.py     # Message queue
│   │   ├── spawn.py       # Spawn manager
│   │   └── send_message.py # Message sender
│   ├── tool/               # Tool system
│   │   ├── base.py        # Tool base class
│   │   ├── registry.py    # Tool registry
│   │   └── builtin/       # Builtin tools
│   │       ├── bash.py
│   │       ├── read.py
│   │       ├── write.py
│   │       ├── edit.py
│   │       ├── glob.py
│   │       └── grep.py
│   └── types/             # Type definitions
│       ├── agent.py
│       ├── message.py
│       └── tool.py
├── docs/                  # Documentation
└── pyproject.toml
```

## Configuration

Config file located at: `~/.ccmas/config.json`

### OpenAI Compatible API Examples

```bash
# MiniMax
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_KEY --model MiniMax-text-01

# DeepSeek
ccmas --api-base https://api.deepseek.com/v1 --api-key YOUR_KEY --model deepseek-chat

# Local model
ccmas --api-base http://localhost:8000/v1 --model llama3
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Code check
ruff check src/

# Type check
mypy src/
```

## Feature Comparison

| Feature               | Reference | CCMAS |
| --------------------- | --------- | ----- |
| AutoCompact           | Yes       | Yes   |
| Token Budget          | Yes       | Yes   |
| Memory System         | Yes       | Yes   |
| Skill System          | Yes       | Yes   |
| Tmux Teammate         | Yes       | Yes   |
| Hooks System          | Yes       | Yes   |
| Error Recovery        | Yes       | Yes   |
| CLAUDE.md Multi-level | Yes       | Yes   |
| MCP Tools             | Yes       | No    |

## OpenClaw Integration

CCMAS supports integration with external task coordination tools like OpenClaw via `state.json`.

When running with `--task-id`, CCMAS creates `~/.ccmas/projects/{hash}/state.json` to track task status:

```json
{
  "task_id": "module_auth_v1",
  "status": "running",
  "summary": "",
  "errors": [],
  "started_at": "2026-04-08T00:10:00Z",
  "updated_at": "2026-04-08T00:10:00Z"
}
```

External tools can poll this file to monitor CCMAS task execution progress.

## License

MIT License
