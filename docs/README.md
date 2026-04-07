# CCMAS 文档中心

欢迎来到 CCMAS（Multi-Agent System）文档中心。本文档提供了关于 CCMAS Python CLI 的全面指南。

## 项目简介

CCMAS 是一个基于 Python 的多智能体系统命令行工具，参考了 Claude Code 源码，复刻了多智能体系统的核心机制。它支持多种 LLM 后端（OpenAI、Ollama、vLLM、MiniMax、DeepSeek等），提供完整的 Agent 系统、Memory 系统、AutoCompact 自动压缩、Token Budget 预算控制等功能。

## 文档索引

### 入门指南
- [安装指南](installation.md) - 如何安装和配置 CCMAS
- [使用指南](usage.md) - 基本使用方法和 CLI 命令
- [配置说明](configuration.md) - 配置文件详解和环境变量

### 核心概念
- [架构概览](architecture.md) - 系统整体架构设计
- [Agent 系统解析](agent_system.md) - Agent 类型、定义和执行机制
- [上下文隔离解析](context_isolation.md) - 上下文管理和隔离机制
- [工具系统解析](tool_system.md) - 工具注册、执行和扩展
- [Query 循环解析](query_loop.md) - 查询循环和对话管理
- [LLM 集成解析](llm_integration.md) - 大语言模型客户端集成
- [Memory 系统解析](memory_system.md) - 记忆系统的使用和配置
- [Skill 系统解析](skill_system.md) - 技能系统的使用和创建
- [Hooks 系统解析](hooks_system.md) - 钩子系统的使用和配置

### 示例代码
- [基本使用示例](examples/basic_usage.py) - 入门示例和常见用法
- [多智能体示例](examples/multi_agent.py) - 多 Agent 协作示例
- [自定义 Agent 示例](examples/custom_agent.py) - 创建自定义 Agent 的完整示例
- [Tmux Teammate 示例](examples/tmux_teammate.py) - Tmux 并行 Agent 示例
- [Memory 使用示例](examples/memory_usage.py) - Memory 系统使用示例

## 快速开始

```bash
# 安装 CCMAS
pip install -e .

# 启动交互模式
ccmas

# 执行单个任务
ccmas "解释量子计算的基本原理"

# Token Budget 预算控制
ccmas "+500k 实现一个 Web 服务器"

# 使用 Ollama 后端
ccmas --ollama --model llama3

# 使用自定义 API
ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_KEY --model MiniMax-M2.7
```

## 核心功能

| 功能 | 说明 |
|------|------|
| MAS 工作逻辑 | 五种子代理模式：Fork、Named、In-process、Tmux、Remote |
| AutoCompact | 对话过长时自动生成摘要 |
| Token Budget | 支持 +500k、use 2M tokens 语法 |
| Memory 系统 | MEMORY.md 索引，user/feedback/project/reference 四种类型 |
| Skill 系统 | /skill-name 调用预设技能 |
| Tmux Teammate | 真正的多终端并行 Agent |
| Hooks 系统 | PreTool/PostTool 钩子 |
| 错误恢复 | 自动重试、断点保存 |
| CLAUDE.md 多级 | 目录树任意位置创建 CLAUDE.md |

## 项目结构

```
ccmas-python-cli/
├── src/ccmas/
│   ├── agent/              # Agent 系统
│   ├── cli/                # CLI 入口
│   ├── context/            # 上下文隔离
│   ├── coordinator/        # Coordinator 模式
│   ├── hooks/             # Hooks 系统
│   ├── llm/                # LLM 客户端
│   ├── memory/             # Memory 系统
│   ├── permission/         # 权限系统
│   ├── prompt/             # 系统提示词
│   ├── query/              # Query 循环
│   ├── skill/              # Skill 系统
│   ├── teammate/           # Teammate 系统
│   ├── tool/               # 工具系统
│   └── types/              # 类型定义
├── docs/                   # 文档
└── examples/               # 示例代码
```

## 配置

配置文件位于: `~/.ccmas/config.json`

## 获取帮助

- 查看 GitHub Issues
- 阅读完整文档
- 参考示例代码

---

**版本**: 0.2.0
**最后更新**: 2026-04-07
