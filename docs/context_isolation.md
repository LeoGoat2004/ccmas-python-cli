# 上下文隔离解析

本文档深入解析 CCMAS 的上下文隔离机制，这是实现安全并发多 Agent 执行的核心技术。

## 为什么需要上下文隔离

### 问题场景

在多 Agent 并发执行时，如果没有上下文隔离：

```python
# 没有隔离的问题
Agent A 正在执行 ──► 全局状态被修改
                          │
Agent B 正在执行 ──► 读取到 Agent A 的状态
                          │
结果：Agent B 的行为受到 Agent A 的干扰
```

### 解决方案

使用上下文隔离后：

```python
# 有隔离的正确行为
Agent A 上下文 ──► Agent A 执行 ──► 独立状态
      │                                │
      │ 隔离                           │ 隔离
      │                                │
Agent B 上下文 ──► Agent B 执行 ──► 独立状态
```

## 核心技术：contextvars

CCMAS 使用 Python 的 `contextvars` 模块实现上下文隔离，类似于 Node.js 的 `AsyncLocalStorage`。

### contextvars 简介

```python
from contextvars import ContextVar

# 创建上下文变量
agent_context_var: ContextVar[Optional[AgentContext]] = ContextVar(
    'agent_context', 
    default=None
)

# 设置值
token = agent_context_var.set(context)

# 获取值
current_context = agent_context_var.get()

# 重置值
agent_context_var.reset(token)
```

### 为什么不用全局变量

**全局变量的问题**：
```python
# 全局状态 - 并发不安全
_current_agent: Optional[AgentContext] = None

def set_agent(ctx):
    global _current_agent
    _current_agent = ctx  # 会被并发覆盖！

def get_agent():
    return _current_agent
```

**contextvars 的优势**：
```python
# contextvars - 并发安全
agent_context_var: ContextVar[Optional[AgentContext]] = ContextVar(
    'agent_context', 
    default=None
)

# 每个异步执行链有自己的上下文副本
```

## 上下文类型

### 1. SubagentContext（子 Agent 上下文）

用于通过 Agent 工具创建的子 Agent。

```python
@dataclass
class SubagentContext:
    """
    子 Agent 上下文
    
    子 Agent 在进程内运行，用于快速委派任务
    """
    # Agent UUID
    agent_id: str
    
    # Agent 类型标识
    agent_type: Literal['subagent'] = 'subagent'
    
    # 父会话 ID（用于关联）
    parent_session_id: Optional[str] = None
    
    # 子 Agent 名称（如 "Explore", "Bash"）
    subagent_name: Optional[str] = None
    
    # 是否内置 Agent
    is_built_in: Optional[bool] = None
    
    # 调用请求 ID
    invoking_request_id: Optional[str] = None
    
    # 调用类型：spawn 或 resume
    invocation_kind: Optional[Literal['spawn', 'resume']] = None
    
    # 是否已发送遥测事件
    invocation_emitted: bool = False
```

### 2. TeammateAgentContext（团队成员上下文）

用于多 Agent 协作环境中的团队成员。

```python
@dataclass
class TeammateAgentContext:
    """
    团队成员上下文
    
    团队成员是 Swarm 的一部分，具有团队协调能力
    """
    # 完整 Agent ID（如 "researcher@my-team"）
    agent_id: str
    
    # 显示名称（如 "researcher"）
    agent_name: str
    
    # 所属团队名称
    team_name: str
    
    # 是否需要在实现前进入计划模式
    plan_mode_required: bool
    
    # 团队负责人的会话 ID
    parent_session_id: str
    
    # 是否是团队负责人
    is_team_lead: bool
    
    # Agent 类型标识
    agent_type: Literal['teammate'] = 'teammate'
    
    # UI 颜色
    agent_color: Optional[str] = None
    
    # 调用请求 ID
    invoking_request_id: Optional[str] = None
    
    # 调用类型
    invocation_kind: Optional[Literal['spawn', 'resume']] = None
    
    # 是否已发送遥测事件
    invocation_emitted: bool = False
```

### 3. 上下文联合类型

```python
# 上下文联合类型
AgentContext = Union[SubagentContext, TeammateAgentContext]

# 全局上下文变量
agent_context_var: ContextVar[Optional[AgentContext]] = ContextVar(
    'agent_context', 
    default=None
)
```

## 上下文管理器

### SubagentContextManager

```python
class SubagentContextManager:
    """
    子 Agent 上下文管理器
    
    使用示例：
        with SubagentContextManager(context):
            # 在此代码块内可以访问 context
            ctx = get_agent_context()
            assert ctx is not None
    """
    
    def __init__(self, context: SubagentContext):
        self._context = context
        self._token = None

    def __enter__(self) -> SubagentContext:
        # 进入上下文时设置值
        self._token = agent_context_var.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # 退出上下文时重置值
        if self._token is not None:
            agent_context_var.reset(self._token)

    async def __aenter__(self) -> SubagentContext:
        # 异步版本
        self._token = agent_context_var.set(self._context)
        return self._context

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # 异步版本
        if self._token is not None:
            agent_context_var.reset(self._token)
```

### TeammateContextManager

```python
class TeammateContextManager:
    """
    团队成员上下文管理器
    
    与 SubagentContextManager 类似，但用于团队成员上下文
    """
    
    def __init__(self, context: TeammateAgentContext):
        self._context = context
        self._token = None

    def __enter__(self) -> TeammateAgentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)
```

## 上下文操作函数

### 获取当前上下文

```python
def get_agent_context() -> Optional[AgentContext]:
    """
    获取当前 Agent 上下文
    
    Returns:
        当前上下文，如果不在 Agent 上下文中则返回 None
    """
    return agent_context_var.get()
```

### 类型守卫函数

```python
def is_subagent_context(context: Optional[AgentContext]) -> bool:
    """
    类型守卫：检查上下文是否为 SubagentContext
    """
    return context is not None and context.agent_type == 'subagent'


def is_teammate_context(context: Optional[AgentContext]) -> bool:
    """
    类型守卫：检查上下文是否为 TeammateAgentContext
    """
    return context is not None and context.agent_type == 'teammate'
```

### 在上下文中运行函数

```python
def run_with_agent_context(context: AgentContext, fn: Callable[[], T]) -> T:
    """
    在给定上下文中运行函数
    
    Args:
        context: 要使用的 Agent 上下文
        fn: 要运行的函数
    
    Returns:
        函数的返回值
    """
    token = agent_context_var.set(context)
    try:
        return fn()
    finally:
        agent_context_var.reset(token)
```

## 使用示例

### 基本使用

```python
from ccmas.context.agent_context import SubagentContext, get_agent_context
from ccmas.context.subagent_context import SubagentContextManager

# 创建上下文
context = SubagentContext(
    agent_id="agent_123",
    subagent_name="Explorer",
    is_built_in=True,
)

# 在上下文中执行
with SubagentContextManager(context):
    # 获取当前上下文
    current = get_agent_context()
    print(current.agent_id)  # 输出: agent_123
    print(current.subagent_name)  # 输出: Explorer

# 离开上下文后
outside = get_agent_context()
print(outside)  # 输出: None
```

### 异步使用

```python
async def process_in_context(context: SubagentContext):
    async with SubagentContextManager(context):
        # 异步操作
        result = await some_async_operation()
        
        # 上下文仍然可用
        ctx = get_agent_context()
        print(f"Processing as {ctx.agent_id}")
        
        return result

# 使用
context = SubagentContext(agent_id="async_agent_1", ...)
result = await process_in_context(context)
```

### 嵌套上下文

```python
# 父上下文
parent_context = SubagentContext(
    agent_id="parent_1",
    subagent_name="Parent",
)

with SubagentContextManager(parent_context):
    print(get_agent_context().agent_id)  # parent_1
    
    # 子上下文
    child_context = SubagentContext(
        agent_id="child_1",
        subagent_name="Child",
        parent_session_id=parent_context.agent_id,
    )
    
    with SubagentContextManager(child_context):
        print(get_agent_context().agent_id)  # child_1
    
    # 回到父上下文
    print(get_agent_context().agent_id)  # parent_1
```

### 并发执行

```python
async def run_agent_task(context: SubagentContext, task: str):
    async with SubagentContextManager(context):
        ctx = get_agent_context()
        print(f"Agent {ctx.agent_id} processing: {task}")
        await asyncio.sleep(1)  # 模拟工作
        return f"Result from {ctx.agent_id}"

# 创建多个上下文
contexts = [
    SubagentContext(agent_id=f"agent_{i}", subagent_name=f"Worker_{i}")
    for i in range(5)
]

# 并发执行
tasks = [
    run_agent_task(ctx, f"Task {i}")
    for i, ctx in enumerate(contexts)
]
results = await asyncio.gather(*tasks)

# 每个 Agent 都有自己的独立上下文
```

## 遥测和追踪

### 调用请求追踪

```python
def consume_invoking_request_id() -> Optional[dict[str, Any]]:
    """
    获取当前 Agent 上下文的调用请求 ID - 每个调用只获取一次
    
    稀疏边语义：invokingRequestId 在每个调用的一个 API 
    成功/错误事件上出现，因此下游的非 NULL 值标记了 
    spawn/resume 边界。
    
    Returns:
        包含 invoking_request_id 和 invocation_kind 的字典，
        如果没有则返回 None
    """
    context = get_agent_context()
    if context is None or context.invoking_request_id is None or context.invocation_emitted:
        return None

    # 标记为已发送
    context.invocation_emitted = True
    
    return {
        'invoking_request_id': context.invoking_request_id,
        'invocation_kind': context.invocation_kind,
    }
```

### 日志记录

```python
def get_subagent_log_name() -> Optional[str]:
    """
    获取适合分析日志的子 Agent 名称
    
    Returns:
        内置 Agent 返回类型名称，自定义 Agent 返回 "user-defined"，
        不在子 Agent 上下文中则返回 None
    """
    context = get_agent_context()
    if not is_subagent_context(context) or not context.subagent_name:
        return None
    return context.subagent_name if context.is_built_in else 'user-defined'
```

## 与进程外 Agent 的关系

对于在单独进程中运行的 Agent（如通过 tmux/iTerm2），使用环境变量而不是 contextvars：

```python
# 进程外 Agent 使用环境变量
CLAUDE_CODE_AGENT_ID=researcher@my-team
CLAUDE_CODE_PARENT_SESSION_ID=session_123
```

contextvars 仅用于进程内 Agent（Subagent 和 Teammate）。

## 最佳实践

### 1. 始终使用上下文管理器

```python
# 推荐
with SubagentContextManager(context):
    do_work()

# 不推荐
token = agent_context_var.set(context)
try:
    do_work()
finally:
    agent_context_var.reset(token)
```

### 2. 检查上下文存在性

```python
def do_something():
    context = get_agent_context()
    if context is None:
        # 不在 Agent 上下文中
        return
    
    # 使用上下文
    ...
```

### 3. 使用类型守卫

```python
context = get_agent_context()

if is_subagent_context(context):
    # 现在 context 被类型收窄为 SubagentContext
    print(context.subagent_name)
elif is_teammate_context(context):
    # 现在 context 被类型收窄为 TeammateAgentContext
    print(context.team_name)
```

### 4. 避免长时间持有上下文引用

```python
# 不推荐：长时间持有引用
context = get_agent_context()
await long_running_task()
# 上下文可能已过期

# 推荐：需要时重新获取
await long_running_task()
context = get_agent_context()  # 重新获取
```

### 5. 正确处理异步边界

```python
# contextvars 会自动传播到 async tasks
async def task():
    ctx = get_agent_context()  # 可以获取到上下文

with SubagentContextManager(context):
    # 创建的任务会继承上下文
    asyncio.create_task(task())
```

## 故障排除

### 问题：上下文为 None

**原因**：
- 不在上下文管理器内执行
- 上下文被意外重置
- 跨线程/进程边界（contextvars 不会自动传播）

**解决方案**：
```python
# 确保在上下文管理器内
def ensure_context(fn):
    context = get_agent_context()
    if context is None:
        raise RuntimeError("No agent context available")
    return fn()
```

### 问题：上下文泄漏

**原因**：
- 未正确重置上下文
- 异常导致 `__exit__` 未执行

**解决方案**：
```python
# 确保总是重置
class SafeContextManager:
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._token is not None:
                agent_context_var.reset(self._token)
        except Exception:
            pass  # 忽略重置错误
```

### 问题：并发冲突

**原因**：
- 多个协程同时修改上下文
- 使用了非异步安全的操作

**解决方案**：
```python
# 使用锁保护上下文操作
_context_lock = asyncio.Lock()

async def safe_context_operation():
    async with _context_lock:
        context = get_agent_context()
        # 安全地操作上下文
```

## 总结

上下文隔离是 CCMAS 实现安全并发多 Agent 执行的基础。通过使用 Python 的 `contextvars`，系统能够：

1. **隔离并发 Agent**：每个 Agent 有自己的上下文副本
2. **追踪执行链**：通过上下文传递 Agent 身份信息
3. **支持遥测**：记录 Agent 调用关系和执行边界
4. **保持类型安全**：使用类型守卫进行精确的类型检查

理解上下文隔离机制对于开发自定义 Agent 和扩展 CCMAS 功能至关重要。
