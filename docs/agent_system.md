# Agent 系统解析

本文档深入解析 CCMAS 的 Agent 系统，包括 Agent 类型、定义结构、执行机制以及扩展方法。

## Agent 概述

Agent 是 CCMAS 的核心概念，代表一个能够执行任务的 AI 实体。每个 Agent 具有：
- 唯一的身份标识
- 特定的能力和配置
- 可访问的工具集
- 独立的执行环境

## Agent 类型

### 1. Built-in Agents（内置 Agent）

系统预定义的 Agent，提供常见功能。

```python
@dataclass
class BuiltInAgentDefinition(AgentDefinition):
    kind: AgentKind = AgentKind.BUILTIN
    is_built_in: bool = True
    implementation: Optional[str] = None
```

**内置 Agent 列表**：

| Agent 名称 | 描述 | 主要工具 | 适用场景 |
|------------|------|----------|----------|
| `general-purpose` | 通用目的 Agent | 所有工具 | 日常任务 |
| `code-reviewer` | 代码审查 Agent | read, search, grep | 代码审查 |
| `explorer` | 探索 Agent | read, search, grep, glob, ls | 代码探索 |
| `test-runner` | 测试运行 Agent | bash, read, write | 测试执行 |

### 2. Custom Agents（自定义 Agent）

用户根据需求定义的 Agent。

```python
@dataclass
class CustomAgentDefinition(AgentDefinition):
    kind: AgentKind = AgentKind.CUSTOM
    is_built_in: bool = False
    file_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
```

### 3. Fork Agents（Fork 子 Agent）

动态创建的子 Agent，用于任务委派。

```python
@dataclass
class ForkAgentDefinition(AgentDefinition):
    kind: AgentKind = AgentKind.FORK
    is_built_in: bool = True
    parent_context: Optional[Any] = None
```

### 4. Teammate Agents（团队成员 Agent）

在多 Agent 协作环境中作为团队成员运行的 Agent。

```python
@dataclass
class TeammateAgentContext:
    agent_id: str
    agent_name: str
    team_name: str
    plan_mode_required: bool
    parent_session_id: str
    is_team_lead: bool
    agent_type: Literal['teammate'] = 'teammate'
```

## Agent 配置

### AgentConfig 结构

```python
class AgentConfig(BaseModel):
    model: Optional[str] = None              # 模型标识
    temperature: Optional[float] = None       # 采样温度
    max_tokens: Optional[int] = None          # 最大 token 数
    tools: List[str] = ["*"]                  # 可用工具列表
    permission_mode: PermissionModeType = PermissionModeType.DEFAULT
    system_prompt: Optional[str] = None       # 自定义系统提示词
    max_iterations: Optional[int] = None      # 最大迭代次数
    timeout_seconds: Optional[int] = None     # 超时时间
    metadata: Dict[str, Any] = {}             # 额外元数据
```

### 配置示例

**通用 Agent 配置**：
```python
AgentConfig(
    model=None,  # 继承父级模型
    tools=["*"],  # 所有工具
    permission_mode=PermissionModeType.DEFAULT,
    system_prompt="You are a helpful assistant...",
    max_iterations=50,
)
```

**代码审查 Agent 配置**：
```python
AgentConfig(
    model=None,
    tools=["read", "search", "grep"],  # 只读工具
    permission_mode=PermissionModeType.DEFAULT,
    system_prompt="You are a code review specialist...",
)
```

**测试运行 Agent 配置**：
```python
AgentConfig(
    model=None,
    tools=["bash", "read", "write"],
    permission_mode=PermissionModeType.ACCEPT_EDITS,
    system_prompt="You are a test execution specialist...",
)
```

## Agent 定义详解

### 基础定义结构

```python
@dataclass
class AgentDefinition:
    name: str                           # Agent 名称
    description: str                    # Agent 描述
    kind: AgentKind                     # Agent 类型
    config: AgentConfig                 # Agent 配置
    version: str = "1.0.0"             # 版本
    author: Optional[str] = None        # 作者
    tags: List[str] = []                # 标签
    examples: List[str] = []            # 使用示例
    is_active: bool = True              # 是否激活
```

### 创建 Agent 定义

**内置 Agent**：
```python
GENERAL_PURPOSE_AGENT = BuiltInAgentDefinition(
    name="general-purpose",
    description="A versatile general-purpose agent...",
    kind=AgentKind.BUILTIN,
    config=create_general_purpose_config(),
    version="1.0.0",
    author="CCMAS",
    tags=["builtin", "general", "versatile"],
    examples=[
        "Read the configuration file...",
        "Create a new Python module...",
    ],
    implementation="ccmas.agent.run_agent",
)
```

**自定义 Agent**：
```python
custom_agent = create_custom_agent(
    name="my-custom-agent",
    description="My custom agent for specific tasks",
    config=AgentConfig(
        model="gpt-4",
        tools=["read", "write"],
        system_prompt="Custom system prompt...",
    ),
    file_path="./my-agent.json",
)
```

## Agent 执行机制

### AgentExecutor

`AgentExecutor` 是执行 Agent 的核心类：

```python
class AgentExecutor:
    def __init__(
        self,
        agent: AgentDefinition,                    # Agent 定义
        llm_client: LLMClient,                     # LLM 客户端
        config: Optional[AgentExecutionConfig] = None,
        permission_checker: Optional[PermissionChecker] = None,
        fork_manager: Optional[ForkSubagentManager] = None,
    ):
        ...
```

### 执行流程

```
1. 初始化 Executor
   ├── 准备 LLM 客户端
   ├── 注册可用工具
   └── 设置权限检查器

2. 执行循环
   ├── 获取 LLM 响应
   ├── 检查是否需要工具调用
   ├── 如有工具调用:
   │   ├── 检查权限
   │   ├── 执行工具
   │   └── 添加结果到历史
   └── 重复直到完成或达到最大迭代次数

3. 返回结果
   ├── 成功/失败状态
   ├── 最终消息
   ├── 执行统计
   └── 工具调用记录
```

### 执行代码示例

```python
async def run_agent(
    agent: AgentDefinition,
    messages: List[Message],
    llm_client: LLMClient,
    config: Optional[AgentExecutionConfig] = None,
    permission_checker: Optional[PermissionChecker] = None,
    parent_context: Optional[SubagentContext] = None,
) -> AgentExecutionResult:
    
    # 创建执行器
    executor = AgentExecutor(
        agent=agent,
        llm_client=llm_client,
        config=config,
        permission_checker=permission_checker,
    )
    
    # 创建子 Agent 上下文
    context = create_subagent_context_for_agent(agent, parent_context)
    
    # 在上下文中执行
    with SubagentContextManager(context):
        return await executor.execute(messages)
```

## Fork 子 Agent 机制

### 为什么需要 Fork

Fork 子 Agent 允许：
- 将复杂任务分解为子任务
- 并行执行多个子任务
- 隔离不同任务的上下文
- 实现多 Agent 协作

### Fork 流程

```python
# 1. 创建 Fork Agent 定义
fork_agent = fork_manager.create_fork_agent(
    task="Analyze the error logs",
    config=AgentConfig(tools=["read", "grep"]),
)

# 2. 构建 Fork 消息
fork_messages = build_forked_messages(
    parent_messages=parent_messages,
    task="Analyze the error logs",
    context={"log_file": "/var/log/app.log"},
)

# 3. 执行 Fork
fork_id = fork_manager.spawn_fork(task, messages, executor)
result = await fork_manager.execute_fork(fork_id, executor, messages)
```

### Fork 结果

```python
@dataclass
class ForkResult:
    success: bool
    output: str
    tool_results: List[Dict[str, Any]]
    error: Optional[str] = None
    agent_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
```

## Agent 上下文管理

### 上下文类型

**SubagentContext**：
```python
@dataclass
class SubagentContext:
    agent_id: str                          # Agent UUID
    agent_type: Literal['subagent']        # 类型标识
    parent_session_id: Optional[str]       # 父会话 ID
    subagent_name: Optional[str]           # Agent 名称
    is_built_in: Optional[bool]            # 是否内置
    invoking_request_id: Optional[str]     # 调用请求 ID
    invocation_kind: Optional[Literal['spawn', 'resume']]
    invocation_emitted: bool = False       # 是否已发送遥测
```

**TeammateAgentContext**：
```python
@dataclass
class TeammateAgentContext:
    agent_id: str                          # 完整 Agent ID
    agent_name: str                        # 显示名称
    team_name: str                         # 团队名称
    plan_mode_required: bool               # 是否需要计划模式
    parent_session_id: str                 # 父会话 ID
    is_team_lead: bool                     # 是否是团队负责人
    agent_type: Literal['teammate']
    agent_color: Optional[str]             # UI 颜色
    invoking_request_id: Optional[str]
    invocation_kind: Optional[Literal['spawn', 'resume']]
    invocation_emitted: bool = False
```

### 上下文管理器

```python
class SubagentContextManager:
    """上下文管理器用于在特定上下文中执行代码"""
    
    def __init__(self, context: SubagentContext):
        self._context = context
        self._token = None

    def __enter__(self) -> SubagentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)
```

## 权限模式

### 权限模式类型

```python
class PermissionModeType(str, Enum):
    DEFAULT = "default"                    # 默认，每次询问
    ACCEPT_EDITS = "acceptEdits"          # 自动接受编辑
    BYPASS_PERMISSIONS = "bypassPermissions"  # 绕过权限
    BUBBLE = "bubble"                      # 向上冒泡
    PLAN = "plan"                          # 计划模式
    AUTO = "auto"                          # 自动判断
```

### 权限检查流程

```python
async def _check_permission(
    self,
    tool_name: str,
    arguments: Dict[str, Any],
) -> PermissionResult:
    
    # 1. 检查是否启用权限
    if not self.config.enable_permissions:
        return PermissionResult.allow(mode=PermissionMode.BYPASS_PERMISSIONS)
    
    # 2. 使用权限检查器
    result = await self.permission_checker.check(
        tool_name=tool_name,
        arguments=arguments,
        mode=PermissionMode(self.agent.config.permission_mode.value),
    )
    
    # 3. 处理冒泡模式
    if result.should_bubble and self._bubble_handler:
        return self._bubble_handler.send_bubble_request(...)
    
    return result
```

## 创建自定义 Agent

### 步骤 1：定义配置

```python
from ccmas.agent.definition import AgentConfig, PermissionModeType

my_config = AgentConfig(
    model="gpt-4",
    temperature=0.5,
    tools=["read", "write", "bash"],
    permission_mode=PermissionModeType.ACCEPT_EDITS,
    system_prompt="""You are a specialized agent for data processing.
    
Your responsibilities:
1. Read data files
2. Process and transform data
3. Write results to output files
4. Verify the output

Always follow best practices for data handling.""",
    max_iterations=30,
    metadata={
        "specialization": "data_processing",
        "version": "1.0.0",
    },
)
```

### 步骤 2：创建 Agent 定义

```python
from ccmas.agent.definition import CustomAgentDefinition

my_agent = CustomAgentDefinition(
    name="data-processor",
    description="Specialized agent for data processing tasks",
    kind=AgentKind.CUSTOM,
    config=my_config,
    version="1.0.0",
    author="Your Name",
    tags=["custom", "data", "processing"],
    examples=[
        "Process the CSV file and generate summary statistics",
        "Transform JSON data to XML format",
        "Clean and validate the dataset",
    ],
)
```

### 步骤 3：执行 Agent

```python
from ccmas.agent.run_agent import run_agent
from ccmas.llm.client import OpenAIClient
from ccmas.types.message import UserMessage

# 创建 LLM 客户端
client = OpenAIClient(model="gpt-4")

# 准备消息
messages = [UserMessage(content="Process the data in input.csv")]

# 执行 Agent
result = await run_agent(
    agent=my_agent,
    messages=messages,
    llm_client=client,
)

# 处理结果
if result.success:
    print(f"Success! Output: {result.message.content}")
else:
    print(f"Failed: {result.error}")
```

### 步骤 4：保存 Agent 定义

```python
import json

# 转换为字典
agent_dict = {
    "name": my_agent.name,
    "description": my_agent.description,
    "config": my_agent.config.model_dump(),
    "version": my_agent.version,
    "author": my_agent.author,
    "tags": my_agent.tags,
    "examples": my_agent.examples,
}

# 保存到文件
with open("my-agent.json", "w") as f:
    json.dump(agent_dict, f, indent=2)
```

## Agent 生命周期

```
┌─────────────┐
│   创建      │
│ (Definition)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   配置      │
│ (Config)    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   初始化    │────►│   执行      │
│ (Executor)  │     │ (Running)   │
└─────────────┘     └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ 完成    │  │ 错误    │  │ 取消    │
        │Completed│  │  Error  │  │ Aborted │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┴────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   清理      │
                   │ (Cleanup)   │
                   └─────────────┘
```

## 最佳实践

### 1. Agent 设计原则

- **单一职责**：每个 Agent 专注于特定任务
- **明确边界**：清晰定义 Agent 的能力范围
- **可配置性**：提供灵活的配置选项
- **可测试性**：设计易于测试的 Agent

### 2. 系统提示词编写

- 清晰说明 Agent 的角色和职责
- 提供具体的指导和约束
- 包含示例说明期望的行为
- 保持提示词简洁明了

### 3. 工具选择

- 只授予必要的工具权限
- 使用最小权限原则
- 考虑工具组合的效果

### 4. 错误处理

- 设计优雅的错误恢复机制
- 提供有意义的错误信息
- 记录详细的执行日志

## 总结

CCMAS 的 Agent 系统提供了灵活而强大的机制来定义和执行 AI Agent。通过理解 Agent 类型、配置选项和执行机制，开发者可以创建满足特定需求的自定义 Agent，实现复杂的多 Agent 协作场景。
