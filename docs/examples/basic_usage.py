"""
CCMAS 基本使用示例

本示例展示如何使用 CCMAS 进行基本的对话和任务执行。
"""

import asyncio
from ccmas.llm.client import OpenAIClient
from ccmas.query.loop import QueryLoop, QueryConfig
from ccmas.types.message import UserMessage


async def basic_conversation():
    """
    基本对话示例
    
    展示如何进行简单的多轮对话。
    """
    # 创建 LLM 客户端
    client = OpenAIClient(
        model="gpt-4",
        temperature=0.7,
    )

    # 创建 QueryLoop
    loop = QueryLoop(
        client=client,
        config=QueryConfig(
            max_turns=10,
            enable_streaming=True,
        ),
        system_prompt="You are a helpful assistant.",
    )

    # 准备初始消息
    messages = [
        UserMessage(content="Hello! Can you help me with Python programming?"),
    ]

    # 执行查询
    print("Assistant: ", end="", flush=True)
    async for output in loop.query(messages):
        if isinstance(output, str):
            # 流式文本输出
            print(output, end="", flush=True)
        else:
            # 消息对象
            print(f"\n[Message type: {output.type}]")

    print("\n" + "=" * 50)


async def single_task_example():
    """
    单任务执行示例
    
    展示如何执行单个任务并获取结果。
    """
    client = OpenAIClient(model="gpt-3.5-turbo")
    
    loop = QueryLoop(
        client=client,
        config=QueryConfig(enable_streaming=False),  # 非流式
    )

    messages = [
        UserMessage(content="Explain the concept of recursion in one paragraph."),
    ]

    # 收集完整响应
    full_response = []
    async for output in loop.query(messages):
        if isinstance(output, str):
            full_response.append(output)

    result = "".join(full_response)
    print(f"Response: {result}")

    # 获取查询结果
    query_result = loop.get_result()
    print(f"Turn count: {query_result.turn_count}")
    print(f"State: {query_result.state}")


async def multi_turn_conversation():
    """
    多轮对话示例
    
    展示如何维护对话历史进行多轮交互。
    """
    client = OpenAIClient(model="gpt-4")
    
    loop = QueryLoop(
        client=client,
        system_prompt="You are a coding assistant. Help with programming questions.",
    )

    # 第一轮
    messages = [UserMessage(content="What is a Python decorator?")]
    
    print("User: What is a Python decorator?")
    print("Assistant: ", end="", flush=True)
    
    async for output in loop.query(messages):
        if isinstance(output, str):
            print(output, end="", flush=True)
    
    print("\n")

    # 第二轮（使用更新后的消息历史）
    messages = loop.messages + [UserMessage(content="Can you show me an example?")]
    
    print("User: Can you show me an example?")
    print("Assistant: ", end="", flush=True)
    
    async for output in loop.query(messages):
        if isinstance(output, str):
            print(output, end="", flush=True)
    
    print("\n")


async def with_context():
    """
    带上下文的对话示例
    
    展示如何使用用户上下文和系统上下文。
    """
    client = OpenAIClient(model="gpt-4")
    
    loop = QueryLoop(
        client=client,
        system_prompt="You are a technical assistant.",
        user_context={
            "name": "Developer",
            "expertise": "Python",
            "project": "Web Application",
        },
        system_context={
            "version": "1.0",
            "environment": "development",
        },
    )

    messages = [
        UserMessage(content="What design patterns would you recommend for my project?"),
    ]

    print("Assistant: ", end="", flush=True)
    async for output in loop.query(messages):
        if isinstance(output, str):
            print(output, end="", flush=True)
    print("\n")


async def error_handling():
    """
    错误处理示例
    
    展示如何处理执行过程中的错误。
    """
    try:
        client = OpenAIClient(model="gpt-4")
        loop = QueryLoop(client=client)

        messages = [UserMessage(content="Hello")]

        async for output in loop.query(messages):
            if isinstance(output, str):
                print(output, end="")
            elif hasattr(output, 'content'):
                # 系统错误消息
                print(f"\n[System]: {output.content}")

        # 检查最终状态
        result = loop.get_result()
        if result.state.value == "error":
            print(f"Error occurred: {result.error}")
        elif result.state.value == "completed":
            print("\nConversation completed successfully!")

    except Exception as e:
        print(f"Exception caught: {e}")


async def main():
    """主函数：运行所有示例"""
    print("=" * 60)
    print("CCMAS Basic Usage Examples")
    print("=" * 60)

    examples = [
        ("Basic Conversation", basic_conversation),
        ("Single Task", single_task_example),
        ("Multi-turn Conversation", multi_turn_conversation),
        ("With Context", with_context),
        ("Error Handling", error_handling),
    ]

    for name, example_func in examples:
        print(f"\n{'=' * 60}")
        print(f"Example: {name}")
        print("=" * 60)
        
        try:
            await example_func()
        except Exception as e:
            print(f"Error in {name}: {e}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
