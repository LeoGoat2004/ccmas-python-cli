# CCMAS 文档中心

欢迎来到 CCMAS（Claude Code Multi-Agent System）文档中心。本文档提供了关于 CCMAS Python CLI 的全面指南，帮助您快速上手并充分利用这个强大的多智能体系统。

## 什么是 CCMAS？

CCMAS 是一个基于 Python 的多智能体系统命令行工具，它允许您构建和管理 AI 驱动的应用程序。它支持多种 LLM 后端（OpenAI、Ollama、vLLM），提供灵活的 Agent 系统、上下文隔离、工具系统和 Query 循环等核心功能。

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

### 示例代码
- [基本使用示例](examples/basic_usage.py) - 入门示例和常见用法
- [多智能体示例](examples/multi_agent.py) - 多 Agent 协作示例
- [自定义 Agent 示例](examples/custom_agent.py) - 创建自定义 Agent 的完整示例

## 快速开始

```bash
# 安装 CCMAS
pip install ccmas

# 启动交互模式
ccmas

# 执行单个任务
ccmas "解释量子计算的基本原理"

# 使用 Ollama 后端
ccmas --ollama --model llama2
```

## 核心特性

### 多智能体系统
- 内置多种专业 Agent（通用、代码审查、探索、测试等）
- 支持自定义 Agent 定义
- Fork 子 Agent 机制用于任务委派

### 上下文隔离
- 基于 contextvars 的上下文管理
- 支持 Subagent 和 Teammate 两种上下文类型
- 安全的并发执行环境

### 工具系统
- 内置文件操作、代码执行、搜索等工具
- 可扩展的工具注册机制
- 并发工具执行和超时控制

### 多后端支持
- OpenAI API 兼容
- Ollama 本地部署
- vLLM 高性能推理

## 项目结构

```
ccmas-python-cli/
├── src/ccmas/
│   ├── agent/          # Agent 定义和执行
│   ├── cli/            # 命令行界面
│   ├── context/        # 上下文管理
│   ├── llm/            # LLM 客户端
│   ├── permission/     # 权限管理
│   ├── prompt/         # 提示词管理
│   ├── query/          # 查询循环
│   ├── tool/           # 工具系统
│   └── types/          # 类型定义
├── docs/               # 文档
└── examples/           # 示例代码
```

## 贡献指南

欢迎贡献代码、报告问题或提出改进建议。请遵循以下步骤：

1. Fork 项目仓库
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

CCMAS 使用 MIT 许可证。详见项目根目录的 LICENSE 文件。

## 获取帮助

- 查看 [GitHub Issues](https://github.com/ccmas/ccmas-python-cli/issues)
- 阅读完整文档
- 参考示例代码

---

**版本**: 0.1.0  
**最后更新**: 2026-04-07
