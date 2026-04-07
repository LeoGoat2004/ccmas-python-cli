# CCMAS Python CLI

Claude Code MAS Python CLI 复现 - 一个强大的多智能体系统命令行工具。

## 项目简介

CCMAS (Claude Code Multi-Agent System) Python CLI 是一个对 Claude Code MAS 核心逻辑的 Python 实现。本项目 1:1 复刻了 Claude Code 的多智能体系统核心机制。

### 核心功能

- 🤖 **MAS 工作逻辑 1:1 复刻** - 五种子代理模式
- 🔒 **上下文隔离** - 使用 contextvars 实现
- 🛡️ **权限冒泡机制** - permission_mode='bubble'
- 🔧 **工具系统** - Bash、Read、Write、Edit、Glob、Grep、Agent
- 💬 **交互式 CLI** - 仿照 Claude Code 使用方式
- ⚡ **异步支持** - 基于 asyncio
- 🧠 **Memory 系统** - CCMAS.md 和历史会话管理

## 安装

```bash
pip install -e .
```

## 快速开始

### 首次使用

```bash
# 运行设置向导
ccmas --setup

# 或直接启动（会提示配置）
ccmas
```

### 基本使用

```bash
# 交互式模式
ccmas

# 执行单个任务
ccmas "写一个斐波那契函数"

# 使用 Ollama
ccmas --ollama --model llama3

# 使用自定义 OpenAI 兼容 API（如 MiniMax、DeepSeek）
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_KEY --model MiniMax-M2.7

# 使用 vLLM
ccmas --vllm --api-base http://localhost:8000/v1 --model llama3
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--setup` | 运行设置向导 |
| `--reset` | 重置配置并重新设置 |
| `--workspace`, `-w` | 工作目录 |
| `--model`, `-m` | 模型名称 |
| `--api-base`, `-b` | API 端点 |
| `--api-key`, `-k` | API 密钥 |
| `--ollama` | 使用 Ollama 后端 |
| `--vllm` | 使用 vLLM 后端 |
| `--temperature`, `-t` | 采样温度 (0-2) |
| `--permission-mode`, `-p` | 权限模式 |
| `--continue` | 继续上次会话 |
| `--load-session` | 加载指定历史会话 |
| `--no-memory` | 禁用 Memory 加载 |
| `--verbose`, `-v` | 详细输出 |
| `--version` | 显示版本 |

## Memory 系统

CCMAS 提供智能的 Memory 系统，自动加载项目上下文和历史会话。

### CCMAS.md

在项目根目录创建 `CCMAS.md` 文件，定义项目特定的行为规则和上下文：

```markdown
# CCMAS 项目配置

## 项目概述
本项目是一个...

## 编码规范
- 使用 Python 3.10+
- 遵循 PEP 8 规范

## 特殊指令
...
```

### 历史会话

CCMAS 自动保存会话历史到 `~/.ccmas/history/`，支持：
- 继续上次会话 (`--continue`)
- 加载指定会话 (`--load-session <session_id>`)
- 跨会话保持上下文

### 内存文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `CCMAS.md` | 项目级 | 项目特定规则和上下文 |
| `~/.ccmas/memory/` | 用户级 | 用户全局记忆 |

## 权限模式

- `default` - 标准权限处理
- `acceptEdits` - 自动接受编辑
- `bypassPermissions` - 跳过权限检查
- `bubble` - 权限冒泡到父代理
- `plan` - 规划模式
- `auto` - 自动模式

## 项目结构

```
ccmas-python-cli/
├── src/ccmas/
│   ├── types/           # 类型定义
│   ├── context/         # 上下文隔离
│   ├── tool/            # 工具系统
│   ├── permission/      # 权限系统
│   ├── llm/             # LLM 客户端
│   ├── memory/          # Memory 系统
│   ├── agent/           # Agent 系统
│   ├── teammate/        # Teammate 系统
│   ├── query/           # Query 循环
│   ├── prompt/          # 系统提示词
│   └── cli/             # CLI 入口
├── docs/                 # 文档
└── pyproject.toml
```

## 配置

配置文件位于: `~/.ccmas/config.json`

### OpenAI 兼容 API 示例

```bash
# MiniMax
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_KEY --model MiniMax-text-01

# DeepSeek
ccmas --api-base https://api.deepseek.com/v1 --api-key YOUR_KEY --model deepseek-chat

# 本地模型
ccmas --api-base http://localhost:8000/v1 --model llama3
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check src/

# 类型检查
mypy src/
```

## 致谢

本项目是对 [Claude Code](https://github.com/anthropics/claude-code) MAS 核心逻辑的 Python 复现。
