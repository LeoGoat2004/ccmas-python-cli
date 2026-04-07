"""
CCMAS 自定义 Agent 示例

本示例展示如何创建、配置和使用自定义 Agent。
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional

from ccmas.agent.definition import (
    AgentConfig,
    AgentKind,
    CustomAgentDefinition,
    PermissionModeType,
    create_custom_agent,
)
from ccmas.agent.run_agent import run_agent, AgentExecutionConfig
from ccmas.llm.client import OpenAIClient
from ccmas.types.message import UserMessage, Message
from ccmas.tool.registry import register_tool
from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


# ==================== 自定义工具示例 ====================

class CalculatorTool(Tool):
    """计算器工具 - 执行数学计算"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform mathematical calculations"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)')"
                }
            },
            "required": ["expression"]
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        import math
        import time
        
        expression = args.arguments.get("expression", "")
        start_time = time.time()
        
        try:
            # 安全的数学计算环境
            safe_dict = {
                'sqrt': math.sqrt,
                'pow': math.pow,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                '