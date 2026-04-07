# 架构概览

本文档介绍 CCMAS（Claude Code Multi-Agent System）的整体架构设计，帮助开发者理解系统的组织方式和核心组件。

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   main.py   │  │ commands.py │  │        config.py        │  │
│  │  Entry Point│  │   Commands  │  │    Configuration Mgmt   │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         └─────────────────┴─────────────────────┘                │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────┐
│                      Agent Layer                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ definition  │  │  run_agent  │  │    fork_subagent        │  │
│  │  Agent Def  │  │   Executor  │  │    Subagent Mgmt        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                                │
│  │   loader    │  │  agent_tool │                                │
│  │ Load Agents │  │ Agent Tools │                                │
│  └─────────────┘  └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────┐
│                      Query Layer                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    loop     │  │  tool_exec  │  │    message_builder      │  │
│  │ Query Loop  │  │Tool Executor│  │    Message Builder      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────┐
│                      Core Layer                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │     llm     │  │    tool     │  │       context           │  │
│  │   Clients   │  │   System    │  │       Manager           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                                │
│  │  permission │  │    types    │                                │
│  │   System    │  │   Types     │                                │
│  └─────────────┘  └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## 分层架构

### 1. CLI 层

负责用户交互和命令处理。

**组件**：
- `main.py`: 入口点，参数解析
- `commands.py`: 命令实现（交互模式、单任务模式）
- `config.py`: 配置管理
- `ui.py`: 用户界面和输出格式化

**职责**：
- 解析命令行参数
- 加载和合并配置
- 创建 LLM 客户端
- 启动适当的执行模式

### 2. Agent 层

管理 Agent 的定义、加载和执行。

**组件**：
- `definition.py`: Agent 定义数据结构
- `run_agent.py`: Agent 执行器
- `fork_subagent.py`: 子 Agent 管理
- `loader.py`: Agent 加载器
- `agent_tool.py`: Agent 工具实现
- `builtin/`: 内置 Agent 定义

**Agent 类型**：
1. **Built-in Agents**: 系统预定义的 Agent
   - General Purpose Agent
   - Code Reviewer Agent
   - Explorer Agent
   - Test Runner Agent

2. **Custom Agents**: 用户定义的 Agent
   - 从配置文件加载
   - 自定义系统提示词
   - 自定义工具集

3. **Fork Agents**: 动态创建的子 Agent
   - 继承父 Agent 配置
   - 用于任务委派
   - 独立执行环境

### 3. Query 层

处理查询循环和对话管理。

**组件**：
- `loop.py`: 主查询循环
- `tool_executor.py`: 工具执行器
- `message_builder.py`: 消息构建器

**查询流程**：
1. 接收用户输入
2. 构建消息历史
3. 调用 LLM 生成响应
4. 处理工具调用
5. 循环直到完成

### 4. Core 层

提供核心服务和基础设施。

**LLM 模块** (`llm/`):
- `client.py`: LLM 客户端基类
- `openai.py`: OpenAI API 客户端
- `ollama.py`: Ollama 客户端
- `vllm.py`: vLLM 客户端

**工具模块** (`tool/`):
- `base.py`: 工具基类
- `registry.py`: 工具注册表
- `builtin/`: 内置工具
  - `read.py`: 文件读取
  - `write.py`: 文件写入
  - `bash.py`: 命令执行
  - `edit.py`: 文件编辑
  - `glob.py`: 文件模式匹配
  - `grep.py`: 内容搜索

**上下文模块** (`context/`):
- `agent_context.py`: Agent 上下文定义
- `subagent_context.py`: 子 Agent 上下文管理
- `teammate_context.py`: 团队成员上下文管理

**权限模块** (`permission/`):
- `mode.py`: 权限模式定义
- `checker.py`: 权限检查器
- `bubble.py`: 权限冒泡处理

**类型模块** (`types/`):
- `agent.py`: Agent 类型
- `message.py`: 消息类型
- `tool.py`: 工具类型

## 核心流程

### 1. 启动流程

```
用户输入命令
    │
    ▼
┌─────────────┐
│  main.py    │
│ 解析参数    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  config.py  │
│ 加载配置    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 创建客户端  │
│ (LLMClient) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 选择模式    │
│ 交互/单任务 │
└──────┬──────┘
       │
       ▼
   执行
```

### 2. 查询流程

```
用户消息
    │
    ▼
┌─────────────┐
│MessageBuilder│
│构建消息     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  LLM Client │
│ 生成响应    │
└──────┬──────┘
       │
       ├──────────┐
       │          │
       ▼          ▼
  ┌────────┐  ┌──────────┐
  │ 文本   │  │ 工具调用 │
  │ 响应   │  │          │
  └────────┘  └────┬─────┘
                   │
                   ▼
          ┌─────────────┐
          │ToolExecutor │
          │执行工具     │
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │ 工具结果    │
          │ 添加到历史  │
          └──────┬──────┘
                 │
                 └──────────────┐
                                │
                                ▼
                        ┌─────────────┐
                        │  继续循环   │
                        │ 或完成     │
                        └─────────────┘
```

### 3. Agent 执行流程

```
Agent 定义
    │
    ▼
┌─────────────┐
│AgentExecutor│
│初始化       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│准备LLM客户端│
│注册工具     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│执行循环     │
│(最多N轮)    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│获取LLM响应  │
└──────┬──────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
  ┌────────┐    ┌──────────┐
  │无工具  │    │有工具调用│
  │调用    │    │          │
  └────┬───┘    └────┬─────┘
       │             │
       │             ▼
       │      ┌─────────────┐
       │      │权限检查     │
       │      └──────┬──────┘
       │             │
       │             ▼
       │      ┌─────────────┐
       │      │执行工具     │
       │      └──────┬──────┘
       │             │
       │             ▼
       │      ┌─────────────┐
       │      │添加结果到   │
       │      │消息历史     │
       │      └──────┬──────┘
       │             │
       └─────────────┘
                       │
                       ▼
              ┌─────────────┐
              │返回结果     │
              └─────────────┘
```

## 关键设计模式

### 1. 策略模式

用于不同的 LLM 后端：

```python
class LLMClient(ABC):
    @abstractmethod
    async def complete(self, messages, **kwargs):
        pass

class OpenAIClient(LLMClient): ...
class OllamaClient(LLMClient): ...
class VLLMClient(LLMClient): ...
```

### 2. 工厂模式

用于创建不同类型的 Agent：

```python
def create_builtin_agent(name, description, config, ...): ...
def create_custom_agent(name, description, config, ...): ...
def create_fork_agent(task, config, ...): ...
```

### 3. 注册表模式

用于工具管理：

```python
class ToolRegistry:
    def register(self, tool): ...
    def get(self, name): ...
    def get_all(self): ...
```

### 4. 上下文管理器

用于 Agent 上下文隔离：

```python
class SubagentContextManager:
    def __enter__(self): ...
    def __exit__(self, ...): ...
```

### 5. 会话管理器

用于跨会话的上下文保持：

```python
class SessionManager:
    def save_session(self, session: Session) -> str: ...
    def load_session(self, session_id: str) -> Session: ...
    def list_sessions(self, workspace: Optional[str] = None) -> List[Session]: ...
    def get_latest_session(self, workspace: str) -> Optional[Session]: ...
```

会话数据存储在 `~/.ccmas/history/` 目录，每个会话为一个 JSON 文件。

### 6. 观察者模式

用于流式输出：

```python
async def stream_with_tools(self, messages, ...):
    async for chunk in response:
        yield chunk
```

## 数据流

### 消息流

```
UserMessage ──► AssistantMessage ──► ToolMessage
                    ▲                    │
                    └────────────────────┘
```

### 上下文流

```
Parent Context ──► SubagentContext ──► Execution Context
       │                                        │
       └────────────────────────────────────────┘
                    (通过 contextvars)
```

### 工具流

```
Tool Call ──► Registry Lookup ──► Permission Check ──► Execution ──► Result
```

## 并发模型

### 工具并发执行

```python
# 使用信号量控制并发
semaphore = asyncio.Semaphore(max_concurrent)

async def execute_with_semaphore(tool_call):
    async with semaphore:
        return await execute_tool(tool_call)

# 并发执行所有工具
tasks = [execute_with_semaphore(tc) for tc in tool_calls]
results = await asyncio.gather(*tasks)
```

### 上下文隔离

使用 Python 的 `contextvars` 实现：

```python
# 每个 Agent 有自己的上下文
agent_context_var: ContextVar[Optional[AgentContext]] = ContextVar('agent_context', default=None)

# 在上下文中执行
with SubagentContextManager(context):
    # 此处的代码可以访问 context
    result = await execute()
```

## 扩展点

### 1. 添加新的 LLM 后端

继承 `LLMClient` 并实现必要方法：

```python
class MyLLMClient(LLMClient):
    async def complete(self, messages, **kwargs): ...
    async def stream(self, messages, **kwargs): ...
```

### 2. 添加新的工具

继承 `Tool` 并实现必要方法：

```python
class MyTool(Tool):
    @property
    def name(self): ...
    @property
    def description(self): ...
    async def execute(self, args): ...
```

### 3. 添加新的 Agent 类型

继承 `AgentDefinition` 或相关类：

```python
@dataclass
class MyAgentDefinition(AgentDefinition):
    kind: AgentKind = AgentKind.CUSTOM
    # 自定义字段
```

### 4. 添加 Memory 文件类型

在 `memory/types.py` 中添加新的 MemoryFile 类型：

```python
class CustomMemoryFile(MemoryFile):
    type: str = Field(pattern="^custom$")
    # 自定义字段
```

## 性能考虑

### 1. 连接池

LLM 客户端使用 HTTP 连接池复用连接。

### 2. 并发控制

工具执行使用信号量限制并发数，防止资源耗尽。

### 3. 超时管理

所有网络操作都有超时控制，防止无限等待。

### 4. 流式处理

支持流式响应，减少内存占用和响应延迟。

## 安全考虑

### 1. 权限控制

多级权限模式控制 Agent 的操作能力。

### 2. 上下文隔离

使用 contextvars 确保并发 Agent 之间不会相互干扰。

### 3. 敏感信息保护

API 密钥等敏感信息不保存到配置文件。

### 4. 输入验证

使用 Pydantic 进行严格的输入验证。

## 监控和调试

### 1. 日志记录

详细记录执行流程和错误信息。

### 2. 性能指标

收集 token 使用量、执行时间等指标。

### 3. 错误处理

完善的错误处理和恢复机制。

## 总结

CCMAS 采用分层架构设计，各层职责清晰，通过明确定义的接口进行交互。这种设计使得系统易于扩展和维护，同时保证了并发执行的安全性和性能。
