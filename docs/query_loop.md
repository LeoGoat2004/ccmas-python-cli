# Query 循环解析

本文档深入解析 CCMAS 的 Query 循环机制，这是处理对话流程、管理消息历史和协调工具调用的核心组件。

## Query 循环概述

Query 循环是 CCMAS 的核心执行引擎，负责：
- 管理对话状态
- 处理多轮交互
- 协调工具调用
- 控制执行流程

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Query Loop                              │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Input     │───►│   Process   │───►│   Output    │     │
│  │  Messages   │    │   & Loop    │    │  Messages   │     │
│  └─────────────┘    └──────┬──────┘    └─────────────┘     │
│                            │                                 │
│              ┌─────────────┼─────────────┐                  │
│              │             │             │                  │
│              ▼             ▼             ▼                  │
│       ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│       │   LLM    │  │  Tools   │  │  State   │             │
│       │  Client  │  │ Executor │  │  Manager │             │
│       └──────────┘  └──────────┘  └──────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. QueryLoop 类

```python
class QueryLoop:
    """
    对话管理的主查询循环
    
    处理用户、助手和工具之间的对话流程，
    管理跨多轮的状态和执行
    """

    def __init__(
        self,
        client: LLMClient,
        config: Optional[QueryConfig] = None,
        system_prompt: Optional[str] = None,
        user_context: Optional[Dict[str, str]] = None,
        system_context: Optional[Dict[str, str]] = None,
    ):
        self.client = client
        self.config = config or QueryConfig()
        self.message_builder = MessageBuilder(
            system_prompt=system_prompt,
            user_context=user_context,
            system_context=system_context,
        )
        
        # 状态跟踪
        self.messages: List[Message] = []
        self.turn_count = 0
        self.state = QueryState.RUNNING
        self.abort_signal = asyncio.Event()
        
        # 工具执行器
        self.tool_executor: Optional[StreamingToolExecutor] = None
```

### 2. QueryConfig 配置

```python
@dataclass
class QueryConfig:
    """查询执行配置"""
    
    max_turns: int = 100           # 最大轮数
    max_tokens: Optional[int] = None  # 最大 token 数
    temperature: float = 0.7       # 采样温度
    timeout: float = 300.0         # 超时时间（秒）
    max_concurrent_tools: int = 10 # 最大并发工具数
    enable_streaming: bool = True  # 启用流式输出
    abort_on_error: bool = False   # 错误时中止
```

### 3. QueryState 状态

```python
class QueryState(str, Enum):
    """查询循环状态枚举"""
    
    RUNNING = "running"              # 运行中
    COMPLETED = "completed"          # 已完成
    ABORTED = "aborted"              # 已中止
    ERROR = "error"                  # 出错
    MAX_TURNS_REACHED = "max_turns_reached"  # 达到最大轮数
```

### 4. QueryResult 结果

```python
@dataclass
class QueryResult:
    """查询执行结果"""
    
    state: QueryState
    messages: List[Message] = field(default_factory=list)
    error: Optional[str] = None
    turn_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## 主查询流程

### 1. 入口方法：query()

```python
async def query(
    self,
    messages: List[Message],
) -> AsyncIterator[Union[Message, str]]:
    """
    执行查询循环
    
    这是运行查询的主入口点
    
    Args:
        messages: 对话的初始消息
    
    Yields:
        生成的消息和内容块
    """
    # 初始化状态
    self.messages = list(messages)
    self.turn_count = 0
    self.state = QueryState.RUNNING
    self.abort_signal.clear()

    # 初始化工具执行器
    self.tool_executor = StreamingToolExecutor(
        max_concurrent=self.config.max_concurrent_tools,
        timeout=self.config.timeout,
    )

    try:
        while self.state == QueryState.RUNNING:
            # 检查中止信号
            if self.abort_signal.is_set():
                self.state = QueryState.ABORTED
                break

            # 检查最大轮数
            if self.turn_count >= self.config.max_turns:
                self.state = QueryState.MAX_TURNS_REACHED
                break

            # 执行一轮
            async for output in self._execute_turn():
                yield output

            self.turn_count += 1

    except Exception as e:
        self.state = QueryState.ERROR
        yield SystemMessage(content=f"Query error: {e}")

    finally:
        # 清理
        if self.tool_executor:
            await self.tool_executor.get_remaining_results()
```

### 2. 单轮执行：_execute_turn()

```python
async def _execute_turn(self) -> AsyncIterator[Union[Message, str]]:
    """
    执行单轮查询循环
    
    Yields:
        该轮的消息和内容块
    """
    # 构建 API 消息
    openai_messages = self.message_builder.build_messages(self.messages)
    system = self.message_builder.build_system_prompt()

    # 获取助手响应
    if self.config.enable_streaming:
        async for output in self._stream_response(openai_messages, system):
            yield output
    else:
        async for output in self._complete_response(openai_messages, system):
            yield output
```

## 响应处理

### 1. 流式响应

```python
async def _stream_response(
    self,
    messages: List[Dict[str, Any]],
    system: str,
) -> AsyncIterator[Union[Message, str]]:
    """
    流式获取助手响应
    
    逐步生成内容，提供更好的用户体验
    """
    # 转换消息格式
    msg_objects = self._convert_openai_messages(messages)

    # 累积内容
    accumulated_content = []
    tool_calls: List[ToolCall] = []

    try:
        async for chunk in self.client.stream_with_tools(
            msg_objects,
            system=system,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            if isinstance(chunk, str):
                # 文本内容
                accumulated_content.append(chunk)
                yield chunk  # 实时输出
            elif isinstance(chunk, ToolCall):
                # 工具调用
                tool_calls.append(chunk)

    except Exception as e:
        yield SystemMessage(content=f"Streaming error: {e}")
        return

    # 创建助手消息
    content = "".join(accumulated_content) if accumulated_content else None
    assistant_msg = AssistantMessage(
        content=content,
        tool_calls=tool_calls if tool_calls else None,
    )
    self.messages.append(assistant_msg)
    yield assistant_msg

    # 执行工具（如果有）
    if tool_calls:
        async for output in self._execute_tools(tool_calls):
            yield output
```

### 2. 完整响应（非流式）

```python
async def _complete_response(
    self,
    messages: List[Dict[str, Any]],
    system: str,
) -> AsyncIterator[Union[Message, str]]:
    """
    获取完整助手响应（非流式）
    
    用于不需要实时输出的场景
    """
    msg_objects = self._convert_openai_messages(messages)

    try:
        assistant_msg = await self.client.complete(
            msg_objects,
            system=system,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        self.messages.append(assistant_msg)
        yield assistant_msg

        # 执行工具（如果有）
        if assistant_msg.tool_calls:
            async for output in self._execute_tools(assistant_msg.tool_calls):
                yield output

    except Exception as e:
        yield SystemMessage(content=f"Completion error: {e}")
```

## 工具执行

### _execute_tools()

```python
async def _execute_tools(
    self,
    tool_calls: List[ToolCall],
) -> AsyncIterator[Message]:
    """
    执行工具调用并生成结果
    
    Args:
        tool_calls: 要执行的工具调用列表
    
    Yields:
        包含结果的工具消息
    """
    if not self.tool_executor:
        return

    # 执行工具
    results = await self.tool_executor.execute_tools(
        tool_calls,
        abort_signal=self.abort_signal,
    )

    # 转换结果为消息
    tool_messages = self.tool_executor.handle_tool_results(results)

    # 添加到消息历史并生成
    for msg in tool_messages:
        self.messages.append(msg)
        yield msg
```

## 消息构建器

### MessageBuilder 类

```python
class MessageBuilder:
    """
    为 OpenAI API 构建消息
    
    处理系统提示词、用户上下文和消息格式转换
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        user_context: Optional[Dict[str, str]] = None,
        system_context: Optional[Dict[str, str]] = None,
    ):
        self.system_prompt = system_prompt
        self.user_context = user_context or {}
        self.system_context = system_context or {}

    def build_system_prompt(self) -> str:
        """构建完整的系统提示词"""
        parts = []
        
        if self.system_prompt:
            parts.append(self.system_prompt)
        
        # 添加上下文信息
        if self.system_context:
            parts.append("\nSystem Context:")
            for key, value in self.system_context.items():
                parts.append(f"- {key}: {value}")
        
        if self.user_context:
            parts.append("\nUser Context:")
            for key, value in self.user_context.items():
                parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)

    def build_messages(
        self,
        messages: List[Message],
    ) -> List[Dict[str, Any]]:
        """构建 OpenAI 格式的消息列表"""
        return MessageConverter.to_openai_messages(messages)
```

## 完整执行流程

```
用户输入
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. 初始化 QueryLoop                     │
│    - 设置配置                            │
│    - 初始化工具执行器                      │
│    - 重置状态                            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 2. 主循环 (while state == RUNNING)      │
│                                          │
│    a. 检查中止信号                        │
│    b. 检查最大轮数                        │
│    c. 执行单轮                           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 3. 执行单轮 (_execute_turn)             │
│                                          │
│    a. 构建消息                           │
│    b. 构建系统提示词                      │
│    c. 调用 LLM                          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 4. 处理响应                              │
│                                          │
│    流式模式:                             │
│    - 逐步接收内容块                       │
│    - 实时输出给用户                       │
│    - 累积完整响应                         │
│                                          │
│    非流式模式:                           │
│    - 等待完整响应                         │
│    - 一次性输出                           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 5. 检查工具调用                          │
│                                          │
│    无工具调用:                           │
│    - 添加到消息历史                       │
│    - 本轮结束                            │
│                                          │
│    有工具调用:                           │
│    - 添加到消息历史                       │
│    - 执行工具                            │
│    - 添加结果到历史                       │
│    - 继续下一轮                          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 6. 循环结束条件                          │
│                                          │
│    - 用户中止 (ABORTED)                  │
│    - 达到最大轮数 (MAX_TURNS_REACHED)     │
│    - 发生错误 (ERROR)                    │
│    - 正常完成 (COMPLETED)                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 7. 清理和返回结果                         │
│    - 获取剩余工具结果                     │
│    - 返回 QueryResult                    │
└─────────────────────────────────────────┘
```

## 使用示例

### 基本使用

```python
from ccmas.query.loop import QueryLoop, QueryConfig
from ccmas.llm.client import OpenAIClient
from ccmas.types.message import UserMessage

# 创建 LLM 客户端
client = OpenAIClient(model="gpt-4")

# 创建 QueryLoop
loop = QueryLoop(
    client=client,
