# 工具系统解析

本文档深入解析 CCMAS 的工具系统，包括工具定义、注册机制、执行流程以及自定义工具开发。

## 工具系统概述

工具是 Agent 与外部环境交互的接口，允许 Agent 执行文件操作、命令执行、网络请求等操作。

### 工具系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      Agent Layer                         │
│                    (请求工具调用)                         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     Tool Registry                        │
│                   (工具注册和查找)                         │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Read    │    │  Write   │    │   Bash   │
    │  Tool    │    │  Tool    │    │   Tool   │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Tool Executor                         │
│                   (并发执行工具)                          │
└─────────────────────────────────────────────────────────┘
```

## 工具基类

### Tool 抽象基类

```python
class Tool(ABC):
    """
    工具的抽象基类
    
    所有 CCMAS 工具必须继承此类并实现必要的方法
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        工具参数的 JSON Schema
        
        Returns:
            JSON Schema 字典
        """
        return {"type": "object", "properties": {}, "required": []}

    def get_definition(self) -> ToolDefinition:
        """获取工具定义"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        执行工具
        
        Args:
            args: 工具调用参数
        
        Returns:
            工具执行结果
        """
        pass
```

### 工具调用参数

```python
class ToolCallArgs(BaseModel):
    """工具调用参数"""
    
    tool_call_id: str = Field(..., description="工具调用的唯一 ID")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, 
        description="传递给工具的参数"
    )
```

### 工具执行结果

```python
class ToolExecutionResult(BaseModel):
    """工具执行结果"""
    
    tool_call_id: str = Field(..., description="工具调用 ID")
    tool_name: str = Field(..., description="执行的工具名称")
    output: ToolOutput = Field(..., description="工具输出")
    execution_time_ms: float = Field(
        default=0.0, 
        description="执行时间（毫秒）"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="额外元数据"
    )

    @property
    def is_success(self) -> bool:
        """检查执行是否成功"""
        return not self.output.is_error

    @property
    def is_error(self) -> bool:
        """检查是否发生错误"""
        return self.output.is_error
```

## 内置工具

### 1. Read Tool（文件读取）

```python
class ReadTool(Tool):
    """读取文件内容的工具"""

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Read the contents of a file"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line offset to start reading from",
                    "default": 0
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                    "default": 100
                }
            },
            "required": ["file_path"]
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        file_path = args.arguments.get("file_path")
        offset = args.arguments.get("offset", 0)
        limit = args.arguments.get("limit", 100)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                content = ''.join(lines[offset:offset + limit])
            
            return self._create_result(
                tool_call_id=args.tool_call_id,
                output=self._create_success_output(
                    args.tool_call_id,
                    content
                ),
                execution_time_ms=0,
            )
        except Exception as e:
            return self._create_result(
                tool_call_id=args.tool_call_id,
                output=self._create_error_output(
                    args.tool_call_id,
                    str(e)
                ),
                execution_time_ms=0,
            )
```

### 2. Write Tool（文件写入）

```python
class WriteTool(Tool):
    """写入文件内容的工具"""

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return "Write content to a file"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                },
                "append": {
                    "type": "boolean",
                    "description": "Whether to append to the file",
                    "default": False
                }
            },
            "required": ["file_path", "content"]
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        file_path = args.arguments.get("file_path")
        content = args.arguments.get("content")
        append = args.arguments.get("append", False)
        
        try:
            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(content)
            
            return self._create_result(...)
        except Exception as e:
            return self._create_result(...)
```

### 3. Bash Tool（命令执行）

```python
class BashTool(Tool):
    """执行 bash 命令的工具"""

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute a bash command"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 60
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory"
                }
            },
            "required": ["command"]
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        import asyncio
        
        command = args.arguments.get("command")
        timeout = args.arguments.get("timeout", 60)
        working_dir = args.arguments.get("working_dir")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            output = stdout.decode() if stdout else ""
            if stderr:
                output += f"\nStderr: {stderr.decode()}"
            
            return self._create_result(...)
        except asyncio.TimeoutError:
            return self._create_error_result(...)
        except Exception as e:
            return self._create_error_result(...)
```

## 工具注册表

### ToolRegistry 类

```python
class ToolRegistry:
    """
    工具注册表
    
    提供注册、检索和管理工具的方法
    使用单例模式确保全局唯一
    """

    _instance: Optional[ToolRegistry] = None
    _tools: Dict[str, Tool]

    def __new__(cls) -> ToolRegistry:
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> Optional[Tool]:
        """注销工具"""
        return self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_all_definitions(self) -> List[ToolDefinition]:
        """获取所有工具定义"""
        return [tool.get_definition() for tool in self._tools.values()]

    def has(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
```

### 全局注册表函数

```python
# 全局注册表实例
_global_registry: Optional[ToolRegistry] = None

def get_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry

def register_tool(tool: Tool) -> None:
    """在全局注册表中注册工具"""
    get_registry().register(tool)

def get_tool(name: str) -> Optional[Tool]:
    """从全局注册表获取工具"""
    return get_registry().get(name)

def get_all_tools() -> List[Tool]:
    """获取全局注册表中的所有工具"""
    return get_registry().get_all()
```

## 工具执行器

### ToolExecutor 类

```python
class ToolExecutor:
    """
    查询循环中的工具执行器
    
    处理工具执行、结果处理和错误处理
    """

    def __init__(
        self,
        tools: Optional[List[Tool]] = None,
        max_concurrent: int = 10,
        timeout: float = 300.0,
    ):
        self.tools = tools
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def execute_tool(
        self,
        tool_call: ToolCall,
        abort_signal: Optional[asyncio.Event] = None,
    ) -> ToolExecutionResult:
        """执行单个工具调用"""
        tool_name = tool_call.function.get("name", "")
        tool_call_id = tool_call.id

        # 获取工具
        tool = self._get_tool(tool_name)
        if not tool:
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Tool '{tool_name}' not found",
            )

        # 解析参数
        try:
            arguments = json.loads(tool_call.function.get("arguments", "{}"))
        except json.JSONDecodeError as e:
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Invalid arguments: {e}",
            )

        # 创建工具调用参数
        args = ToolCallArgs(
            tool_call_id=tool_call_id,
            arguments=arguments,
        )

        # 带超时执行
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                tool.execute(args),
                timeout=self.timeout,
            )
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
        except asyncio.TimeoutError:
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Timeout after {self.timeout}s",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
```

### 并发工具执行

```python
async def execute_tools(
    self,
    tool_calls: List[ToolCall],
    abort_signal: Optional[asyncio.Event] = None,
) -> List[ToolExecutionResult]:
    """
    并发执行多个工具调用
    
    使用信号量控制并发数
    """
    if not tool_calls:
        return []

    # 初始化信号量
    if self._semaphore is None:
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    async def execute_with_semaphore(
        tool_call: ToolCall,
    ) -> ToolExecutionResult:
        async with self._semaphore:
            # 检查中止信号
            if abort_signal and abort_signal.is_set():
                return self._create_error_result(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.function.get("name", ""),
                    error_message="Execution aborted",
                )
            return await self.execute_tool(tool_call, abort_signal)

    # 并发执行所有工具
    tasks = [execute_with_semaphore(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 转换异常为错误结果
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(
                self._create_error_result(
                    tool_call_id=tool_calls[i].id,
                    tool_name=tool_calls[i].function.get("name", ""),
                    error_message=f"Execution failed: {result}",
                )
            )
        else:
            final_results.append(result)

    return final_results
```

## 创建自定义工具

### 步骤 1：继承 Tool 基类

```python
from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult

class SearchTool(Tool):
    """搜索文件内容的工具"""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "Search for text patterns in files"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex supported)"
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to match (e.g., '*.py')",
                    "default": "*"
                }
            },
            "required": ["pattern", "path"]
        }
```

### 步骤 2：实现 execute 方法

```python
    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        import re
        import os
        
        pattern = args.arguments.get("pattern")
        path = args.arguments.get("path")
        file_pattern = args.arguments.get("file_pattern", "*")
        
        start_time = time.time()
        matches = []
        
        try:
            if os.path.isfile(path):
                # 搜索单个文件
                matches = self._search_file(path, pattern)
            else:
                # 递归搜索目录
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file_pattern == "*" or file.endswith(file_pattern.lstrip("*")):
                            file_path = os.path.join(root, file)
                            file_matches = self._search_file(file_path, pattern)
                            matches.extend(file_matches)
            
            # 格式化结果
            result_text = self._format_matches(matches)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return self._create_result(
                tool_call_id=args.tool_call_id,
                output=self._create_success_output(
                    args.tool_call_id,
                    result_text
                ),
                execution_time_ms=execution_time_ms,
                metadata={"match_count": len(matches)}
            )
            
        except Exception as e:
            return self._create_result(
                tool_call_id=args.tool_call_id,
                output=self._create_error_output(
                    args.tool_call_id,
                    str(e)
                ),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _search_file(self, file_path: str, pattern: str) -> List[Dict]:
        """在单个文件中搜索"""
        matches = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if re.search(pattern, line):
                        matches.append({
                            "file": file_path,
                            "line": line_num,
                            "content": line.strip()
                        })
        except Exception:
            pass  # 忽略无法读取的文件
        return matches

    def _format_matches(self, matches: List[Dict]) -> str:
        """格式化匹配结果"""
        if not matches:
            return "No matches found"
        
        lines = [f"Found {len(matches)} matches:"]
        for match in matches[:50]:  # 限制结果数量
            lines.append(f"{match['file']}:{match['line']}: {match['content']}")
        
        if len(matches) > 50:
            lines.append(f"... and {len(matches) - 50} more matches")
        
        return "\n".join(lines)
```

### 步骤 3：注册工具

```python
from ccmas.tool.registry import register_tool

# 创建工具实例
search_tool = SearchTool()

# 注册到全局注册表
register_tool(search_tool)

# 或者在 Agent 配置中使用
agent_config = AgentConfig(
    tools=["read", "write", "search"],  # 包含自定义工具
)
```

## 工具定义格式

### ToolDefinition

```python
class ToolDefinition(BaseModel):
    """工具定义，用于向 LLM 描述工具"""
    
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="参数的 JSON Schema"
    )

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI 函数调用格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
```

### OpenAI 格式示例

```json
{
  "type": "function",
  "function": {
    "name": "read",
    "description": "Read the contents of a file",
    "parameters": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "Path to the file to read"
        },
        "offset": {
          "type": "integer",
          "description": "Line offset to start reading from",
          "default": 0
        },
        "limit": {
          "type": "integer",
          "description": "Maximum number of lines to read",
          "default": 100
        }
      },
      "required": ["file_path"]
    }
  }
}
```

## 工具调用流程

```
1. LLM 生成工具调用请求
   {
     "name": "read",
     "arguments": "{\"file_path\": \"/path/to/file\"}"
   }

2. 系统解析工具调用
   ├── 提取工具名称
   ├── 解析参数 JSON
   └── 验证参数

3. 查找工具
   ├── 从注册表获取工具实例
   └── 检查工具是否存在

4. 权限检查
   ├── 检查用户权限
   ├── 检查 Agent 权限模式
   └── 决定是否允许执行

5. 执行工具
   ├── 创建 ToolCallArgs
   ├── 调用 tool.execute()
   └── 处理超时和异常

6. 返回结果
   ├── 格式化输出
   ├── 添加到消息历史
   └── 发送给 LLM
```

## 最佳实践

### 1. 参数设计

- 使用清晰的参数名称
- 提供有意义的描述
- 设置合理的默认值
- 明确标记必需参数

### 2. 错误处理

```python
async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
    try:
        # 验证参数
        if not self._validate_args(args.arguments):
            return self._create_error_result(
                tool_call_id=args.tool_call_id,
                tool_name=self.name,
                error_message="Invalid arguments",
            )
        
        # 执行操作
        result = await self._do_work(args.arguments)
        
        return self._create_success_result(...)
        
    except KnownError as e:
        # 已知错误，返回友好消息
        return self._create_error_result(
            tool_call_id=args.tool_call_id,
            tool_name=self.name,
            error_message=f"Operation failed: {e.user_message}",
        )
    except Exception as e:
        # 未知错误，记录详细信息
        logger.exception("Tool execution failed")
        return self._create_error_result(
            tool_call_id=args.tool_call_id,
            tool_name=self.name,
            error_message="An unexpected error occurred",
        )
```

### 3. 性能优化

- 使用异步 I/O 避免阻塞
- 实现超时控制
- 限制结果大小
- 缓存频繁访问的数据

### 4. 安全性

- 验证所有输入
- 限制文件系统访问
- 控制命令执行权限
- 记录敏感操作

## 故障排除

### 工具未找到

```python
# 检查工具是否已注册
if not get_registry().has("my_tool"):
    print("Tool not registered!")
    register_tool(MyTool())
```

### 参数解析错误

```python
# 验证 JSON 参数
try:
    arguments = json.loads(tool_call.function.get("arguments", "{}"))
except json.JSONDecodeError as e:
    return error_result(f"Invalid JSON: {e}")
```

### 执行超时

```python
# 设置适当的超时时间
try:
    result = await asyncio.wait_for(
        tool.execute(args),
        timeout=30.0,  # 根据操作调整
    )
except asyncio.TimeoutError:
    return error_result("Operation timed out")
```

## 总结

CCMAS 的工具系统提供了：

1. **统一的工具接口**：所有工具继承自 Tool 基类
2. **灵活的注册机制**：支持全局和局部工具注册
3. **并发执行能力**：使用信号量控制并发
4. **完善的错误处理**：统一的错误处理和报告
5. **易于扩展**：简单的自定义工具开发流程

理解工具系统对于扩展 CCMAS 功能和开发自定义 Agent 至关重要。
