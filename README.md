# CCMAS Python CLI

Claude Code MAS Python CLI 复现 - 一个强大的多智能体系统命令行工具。

## 项目简介

CCMAS (Claude Code Multi-Agent System) Python CLI 是一个对 Claude Code MAS 核心逻辑的 Python 实现。本项目 1:1 复刻了 Claude Code 的多智能体系统核心机制，包括：

- 五种子代理模式（Fork Subagent、Named Agent、Remote Agent、In-process Teammate、Tmux Teammate）
- 上下文隔离机制（使用 contextvars）
- 权限冒泡机制
- 工具注册与治理系统
- Query 循环

## 功能特性

- 🤖 **MAS 工作逻辑 1:1 复刻** - 五种子代理模式完整实现
- 🔒 **上下文隔离** - 使用 contextvars 实现 AsyncLocalStorage 模拟
- 🛡️ **权限冒泡机制** - permission_mode='bubble' 时权限请求冒泡到父代理
- 🔧 **工具系统** - Bash、Read、Write、Agent 等内置工具
- 💬 **交互式对话** - 提供丰富的命令行交互体验
- 🎨 **美观输出** - 使用 Rich 库提供美观的终端输出
- ⚡ **异步支持** - 基于 asyncio 的高性能异步处理

## 安装说明

```bash
# 克隆仓库
git clone <your-repo-url>
cd ccmas-python-cli

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

## 快速开始

### 基本使用

```bash
# 启动交互式会话
ccmas

# 执行单个任务
ccmas "Write a Python function to calculate fibonacci numbers"

# 查看帮助
ccmas --help
```

### 使用 OpenAI 兼容 API

CCMAS 支持所有 OpenAI 格式的模型，包括 MiniMax、DeepSeek 等：

```bash
# 使用 MiniMax
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_API_KEY --model MiniMax-text-01 "任务描述"

# 使用 DeepSeek
ccmas --api-base https://api.deepseek.com/v1 --api-key YOUR_API_KEY --model deepseek-chat "任务描述"

# 使用本地部署的模型
ccmas --api-base http://localhost:8000/v1 --model llama3 "任务描述"
```

### 使用 Ollama

```bash
# 使用 Ollama 后端
ccmas --ollama --model llama3 "任务描述"
```

### 使用 vLLM

```bash
# 使用 vLLM 后端
ccmas --vllm --api-base http://localhost:8000/v1 --model llama3 "任务描述"
```

## 项目结构

```
ccmas-python-cli/
├── src/ccmas/           # 核心代码
│   ├── types/           # 类型定义（Message, Agent, Tool）
│   ├── context/         # 上下文隔离（使用 contextvars）
│   ├── tool/            # 工具系统（Bash, Read, Write, Agent）
│   ├── permission/      # 权限系统（6种权限模式 + 冒泡机制）
│   ├── llm/             # LLM 客户端（OpenAI/vLLM/Ollama）
│   ├── agent/           # Agent 系统（五种代理模式）
│   ├── teammate/        # Teammate 系统（Mailbox 通信）
│   ├── query/           # Query 循环
│   ├── prompt/          # 系统提示词（复用 CC 源码）
│   └── cli/             # CLI 入口
├── docs/                # 文档（使用指南 + 代码解析）
└── pyproject.toml       # 项目配置
```

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--model`, `-m` | 指定模型 |
| `--api-base`, `-b` | API 端点（如 https://api.minimax.chat/v1） |
| `--api-key`, `-k` | API 密钥 |
| `--ollama` | 使用 Ollama 后端 |
| `--vllm` | 使用 vLLM 后端 |
| `--temperature`, `-t` | 采样温度 (0-2) |
| `--max-tokens` | 最大生成 token 数 |
| `--permission-mode`, `-p` | 权限模式 |
| `--output`, `-o` | 输出文件路径 |
| `--verbose`, `-v` | 详细输出 |

## 权限模式

- `default` - 标准权限处理，需要用户确认
- `acceptEdits` - 自动接受编辑操作
- `bypassPermissions` - 跳过所有权限检查
- `bubble` - 将权限请求冒泡到父代理
- `plan` - 规划操作的权限模式
- `auto` - 基于上下文的自动权限处理

## 开发指南

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff check src/
ruff format src/

# 类型检查
mypy src/
```

## 致谢

本项目是对 [Claude Code](https://github.com/anthropics/claude-code) MAS 核心逻辑的 Python 复现，仅供学习研究使用。
