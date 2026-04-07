# LLM 集成解析

本文档深入解析 CCMAS 的 LLM（大语言模型）集成机制，包括客户端架构、支持的提供商和扩展方法。

## LLM 集成概述

CCMAS 设计了一个抽象的 LLM 客户端层，支持多种后端提供商：
- OpenAI API（包括兼容服务）
- Ollama（本地部署）
- vLLM（高性能推理）

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  QueryLoop  │  │AgentExecutor│  │   Other Components  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         └─────────────────┴─────────────────────┘            │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      LLM Client Layer                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              LLMClient (Abstract Base)               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  complete() │  │  stream()   │  │stream_with_ │  │   │
│  │  │             │  │             │  │   tools()   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │                                          │
│      ┌────────────┼────────────┐                            │
│      │            │            │                            │
│      ▼            ▼            ▼                            │
│  ┌────────┐  ┌────────┐  ┌────────┐                        │
│  │ OpenAI │  │ Ollama │  │  vLLM  │                        │
│  │ Client │  │ Client │  │ Client │                        │
│  └────────┘  └────────┘  └────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## LLMClient 抽象基类

### 基础结构

```python
class LLMClient(ABC):
    """
    LLM 客户端基类
    
    定义 LLM 客户端接口，支持流式响应和工具调用
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tool_registry = ToolRegistry()
        self.extra_params = kwargs

        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

    def register_tool(self, tool: ToolDefinition) -> None:
        """注册工具"""
        self.tool_registry.register(tool)

    def unregister_tool(self, name: str) -> Optional[ToolDefinition]:
        """注销工具"""
        return self.tool_registry.unregister(name)

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """生成完整响应"""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """生成流式响应"""
        pass
```

## OpenAI 客户端

### OpenAIClient 实现

```python
class OpenAIClient(LLMClient):
    """
    OpenAI API 客户端
    
    实现 LLM 客户端接口，支持 OpenAI API 和兼容服务
    """

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, temperature, max_tokens, tools, **kwargs)

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """生成完整响应"""
        openai_messages = self._prepare_messages(messages, system)
        tools = self._prepare_tools()

        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if tools:
            params["tools"] = tools

        response = await self.client.chat.completions.create(**params)

        # 提取响应数据
        choice = response.choices[0]
        content = choice.message.content
        tool_calls = None

        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function={
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                )
                for tc in choice.message.tool_calls
            ]

        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            stop_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """生成流式响应"""
        openai_messages = self._prepare_messages(messages, system)

        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def stream_with_tools(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Union[str, ToolCall]]:
        """
        生成带工具调用的流式响应
        
        同时返回文本内容和工具调用
        """
        openai_messages = self._prepare_messages(messages, system)
        tools = self._prepare_tools()

        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if tools:
            params["tools"] = tools

        stream = await self.client.chat.completions.create(**params)

        # 累积工具调用
        tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 生成文本内容
            if delta.content:
                yield delta.content

            # 处理工具调用
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index

                    if idx not in tool_calls_accumulator:
                        tool_calls_accumulator[idx] = {
                            "id": tc.id or "",
                            "type": tc.type or "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    if tc.id:
                        tool_calls_accumulator[idx]["id"] = tc.id

                    if tc.function:
                        if tc.function.name:
                            tool_calls_accumulator[idx]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_accumulator[idx]["function"]["arguments"] += tc.function.arguments

        # 生成完成的工具调用
        for idx in sorted(tool_calls_accumulator.keys()):
            tc_data = tool_calls_accumulator[idx]
            yield ToolCall(
                id=tc_data["id"],
                type=tc_data["type"],
                function=tc_data["function"],
            )
```

## Ollama 客户端

### OllamaClient 实现

```python
class OllamaClient(LLMClient):
    """
    Ollama 本地部署客户端
    
    支持本地运行的 Ollama 服务
    """

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, temperature, max_tokens, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient()

    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """生成完整响应"""
        ollama_messages = self._convert_to_ollama_messages(messages, system)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        if self.max_tokens:
            payload["options"]["num_predict"] = self.max_tokens

        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return AssistantMessage(
            content=data["message"]["content"],
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
        )

    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """生成流式响应"""
        ollama_messages = self._convert_to_ollama_messages(messages, system)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": self.temperature,
            },
        }

        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

    def _convert_to_ollama_messages(
        self,
        messages: List[Message],
        system: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """转换为 Ollama 消息格式"""
        ollama_messages = []

        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            if isinstance(msg, UserMessage):
                ollama_messages.append({
                    "role": "user",
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                })
            elif isinstance(msg, AssistantMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content) if msg.content else ""
                ollama_messages.append({"role": "assistant", "content": content})

        return ollama_messages
```

## vLLM 客户端

### VLLMClient 实现

```python
class VLLMClient(OpenAIClient):
    """
    vLLM 高性能推理客户端
    
    vLLM 提供 OpenAI 兼容的 API，因此继承 OpenAIClient
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "not-needed",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
```

## 消息转换

### MessageConverter 类

```python
class MessageConverter:
    """
    消息转换器
    
    提供消息格式转换工具
    """

    @staticmethod
    def to_openai_messages(messages: List[Message]) -> List[Dict[str, Any]]:
        """转换为 OpenAI 格式"""
        result = []
        for msg in messages:
            if isinstance(msg, UserMessage):
                result.append({
                    "role": "user",
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                })
            elif isinstance(msg, AssistantMessage):
                openai_msg: Dict[str, Any] = {"role": "assistant"}
                if msg.content:
                    openai_msg["content"] = msg.content
                if msg.tool_calls:
                    openai_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": tc.function,
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(openai_msg)
            elif isinstance(msg, ToolMessage):
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                })
        return result

    @staticmethod
    def from_openai_format(data: Dict[str, Any]) -> Message:
        """从 OpenAI 格式创建消息"""
        role = data.get("role")

        if role == "user":
            return UserMessage(content=data.get("content", ""))
        elif role == "assistant":
            tool_calls = None
            if "tool_calls" in data:
                tool_calls = [ToolCall(**tc) for tc in data["tool_calls"]]
            return AssistantMessage(
                content=data.get("content"),
                tool_calls=tool_calls,
            )
        elif role == "tool":
            return ToolMessage(
                tool_call_id=data.get("tool_call_id", ""),
                content=data.get("content", ""),
            )
        else:
            raise ValueError(f"Unknown role: {role}")
```

## 工具注册

### 工具注册到 LLM

```python
class LLMClient:
    def _prepare_tools(self) -> Optional[List[Dict[str, Any]]]:
        """
        准备工具供 API 调用
        
        Returns:
            OpenAI 格式的工具列表，如果没有工具则返回 None
        """
        tools = self.tool_registry.get_all()
        if not tools:
            return None

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
```

## 创建自定义 LLM 客户端

### 步骤 1：继承 LLMClient

```python
from ccmas.llm.client import LLMClient

class MyCustomLLMClient(LLMClient):
    """自定义 LLM 客户端示例"""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """实现完整响应生成"""
        # 转换消息格式
        formatted_messages = self._format_messages(messages, system)

        # 调用 API
        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": formatted_messages,
                "temperature": self.temperature,
            },
        )
        response.raise_for_status()
        data = response.json()

        # 解析响应
        return AssistantMessage(
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage", {}),
        )

    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """实现流式响应生成"""
        formatted_messages = self._format_messages(messages, system)

        async with self.client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": formatted_messages,
                "temperature": self.temperature,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "choices" in data and data["choices"]:
                        content = data["choices"][0].get("delta", {}).get("content")
                        if content:
                            yield content

    def _format_messages(
        self,
        messages: List[Message],
        system: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """格式化消息为 API 格式"""
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})

        for msg in messages:
            if isinstance(msg, UserMessage):
                formatted.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AssistantMessage):
                formatted.append({"role": "assistant", "content": str(msg.content) if msg.content else ""})

        return formatted
```

### 步骤 2：注册和使用

```python
from ccmas.cli.config import CLIConfig

# 在配置中指定自定义客户端
def create_client(config: CLIConfig) -> LLMClient:
    if config.backend == "custom":
        return MyCustomLLMClient(
            model=config.model,
            api_key=config.api_key,
            base_url=config.api_base,
        )
    # ... 其他客户端
```

## 最佳实践

### 1. 错误处理

```python
async def complete_with_retry(
    self,
    messages: List[Message],
    max_retries: int = 3,
    **kwargs: Any,
) -> AssistantMessage:
    """带重试的完整响应生成"""
    for attempt in range(max_retries):
        try:
            return await self.complete(messages, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
```

### 2. 超时控制

```python
async def complete_with_timeout(
    self,
    messages: List[Message],
    timeout: float = 60.0,
    **kwargs: Any,
) -> AssistantMessage:
    """带超时的完整响应生成"""
    return await asyncio.wait_for(
        self.complete(messages, **kwargs),
        timeout=timeout,
    )
```

### 3. Token 使用监控

```python
class TokenUsageTracker:
    """Token 使用追踪器"""

    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def record_usage(self, usage: Dict[str, int]) -> None:
        """记录使用情况"""
        self.total_prompt_tokens += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
        }
```

## 故障排除

### 连接问题

```python
# 检查连接
async def check_connection(client: LLMClient) -> bool:
    try:
        await client.complete(
            [UserMessage(content="Hi")],
            max_tokens=1,
        )
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False
```

### 响应解析错误

```python
# 安全的响应解析
def safe_parse_response(response_data: Dict[str, Any]) -> AssistantMessage:
    try:
        content = response_data["choices"][0]["message"]["content"]
        usage = response_data.get("usage", {})
        return AssistantMessage(content=content, usage=usage)
    except (KeyError, IndexError) as e:
        raise ValueError(f"Invalid response format: {e}")
```

## 总结

CCMAS 的 LLM 集成提供了：

1. **统一的客户端接口**：通过抽象基类支持多种后端
2. **完整的 OpenAI 兼容性**：支持标准 API 和流式响应
3. **本地部署支持**：Ollama 和 vLLM 集成
4. **工具调用支持**：Function calling 能力
5. **易于扩展**：简单的自定义客户端开发

理解 LLM 集成机制对于使用不同模型和部署场景至关重要。
