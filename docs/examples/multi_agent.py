"""
CCMAS 多智能体示例

本示例展示如何使用 CCMAS 进行多 Agent 协作和任务委派。
"""

import asyncio
from typing import List
from ccmas.agent.definition import (
    AgentConfig,
    AgentKind,
    BuiltInAgentDefinition,
    PermissionModeType,
)
from ccmas.agent.run_agent import run_agent, AgentExecutionConfig
from ccmas.agent.fork_subagent import ForkSubagentManager, run_fork_subagent
from ccmas.llm.client import OpenAIClient
from ccmas.types.message import UserMessage, Message


# 定义专门的 Agent
EXPLORER_AGENT = BuiltInAgentDefinition(
    name="explorer",
    description="Explores and analyzes codebase structure",
    kind=AgentKind.BUILTIN,
    config=AgentConfig(
        model=None,
        tools=["read", "search", "grep", "glob", "ls"],
        permission_mode=PermissionModeType.DEFAULT,
        system_prompt="""You are a codebase explorer. Your job is to:
1. Navigate and understand code structure
2. Find relevant files and code
3. Map dependencies and relationships
4. Provide clear summaries of findings

Be thorough in your exploration and provide comprehensive reports.
Always explain your findings in detail.""",
        max_iterations=20,
    ),
    tags=["builtin", "explore", "analysis"],
)

CODE_REVIEWER_AGENT = BuiltInAgentDefinition(
    name="code-reviewer",
    description="Reviews code for quality and issues",
    kind=AgentKind.BUILTIN,
    config=AgentConfig(
        model=None,
        tools=["read", "search", "grep"],
        permission_mode=PermissionModeType.DEFAULT,
        system_prompt="""You are a code review specialist. Your job is to review code changes and provide:
1. Analysis of the changes
2. Potential issues or bugs
3. Suggestions for improvement
4. Best practice recommendations

Focus on code quality, maintainability, performance, and security.
Be constructive and specific in your feedback.""",
        max_iterations=15,
    ),
    tags=["builtin", "review", "quality"],
)

DOCUMENTATION_AGENT = BuiltInAgentDefinition(
    name="documentation-writer",
    description="Writes and improves documentation",
    kind=AgentKind.BUILTIN,
    config=AgentConfig(
        model=None,
        tools=["read", "write", "search"],
        permission_mode=PermissionModeType.ACCEPT_EDITS,
        system_prompt="""You are a technical documentation specialist. Your job is to:
1. Write clear and comprehensive documentation
2. Improve existing documentation
3. Create API documentation
4. Write usage examples

Focus on clarity, completeness, and accuracy.
Use proper formatting and structure.""",
        max_iterations=20,
    ),
    tags=["builtin", "documentation", "writing"],
)


async def parallel_agent_execution():
    """
    并行 Agent 执行示例
    
    展示如何同时运行多个 Agent 处理不同任务。
    """
    print("=" * 60)
    print("Parallel Agent Execution")
    print("=" * 60)

    client = OpenAIClient(model="gpt-4")

    # 定义不同 Agent 的任务
    tasks = [
        (EXPLORER_AGENT, "Explore the project structure and identify main components"),
        (CODE_REVIEWER_AGENT, "Review the main.py file for code quality"),
        (DOCUMENTATION_AGENT, "Check if README.md needs updates"),
    ]

    # 并行执行所有 Agent
    async def run_agent_task(agent, task_description):
        print(f"\nStarting {agent.name}...")
        messages = [UserMessage(content=task_description)]
        
        result = await run_agent(
            agent=agent,
            messages=messages,
            llm_client=client,
            config=AgentExecutionConfig(max_iterations=10),
        )
        
        return {
            "agent": agent.name,
            "success": result.success,
            "output": result.message.content if result.message else result.error,
            "iterations": result.iterations,
        }

    # 并发执行
    results = await asyncio.gather(*[
        run_agent_task(agent, task)
        for agent, task in tasks
    ])

    # 输出结果
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    
    for result in results:
        print(f"\n{result['agent']}:")
        print(f"  Success: {result['success']}")
        print(f"  Iterations: {result['iterations']}")
        print(f"  Output: {result['output'][:200]}..." if len(result['output']) > 200 else f"  Output: {result['output']}")


async def sequential_agent_pipeline():
    """
    顺序 Agent 流水线示例
    
    展示如何让多个 Agent 按顺序协作完成任务。
    """
    print("\n" + "=" * 60)
    print("Sequential Agent Pipeline")
    print("=" * 60)

    client = OpenAIClient(model="gpt-4")

    # 步骤 1: 探索代码
    print("\nStep 1: Exploration")
    explore_messages = [
        UserMessage(content="Explore the src directory and identify the main modules")
    ]
    
    explore_result = await run_agent(
        agent=EXPLORER_AGENT,
        messages=explore_messages,
        llm_client=client,
    )
    
    exploration_summary = explore_result.message.content if explore_result.message else ""
    print(f"Exploration complete. Found: {exploration_summary[:200]}...")

    # 步骤 2: 代码审查（基于探索结果）
    print("\nStep 2: Code Review")
    review_messages = [
        UserMessage(content=f"Based on this exploration:\n{exploration_summary}\n\nReview the architecture and suggest improvements.")
    ]
    
    review_result = await run_agent(
        agent=CODE_REVIEWER_AGENT,
        messages=review_messages,
        llm_client=client,
    )
    
    review_feedback = review_result.message.content if review_result.message else ""
    print(f"Review complete. Feedback: {review_feedback[:200]}...")

    # 步骤 3: 生成文档（基于审查结果）
    print("\nStep 3: Documentation")
    doc_messages = [
        UserMessage(content=f"Based on this code review:\n{review_feedback}\n\nCreate documentation for the architecture.")
    ]
    
    doc_result = await run_agent(
        agent=DOCUMENTATION_AGENT,
        messages=doc_messages,
        llm_client=client,
    )
    
    print(f"Documentation complete!")
    print(f"\nFinal output preview:\n{doc_result.message.content[:300]}..." if doc_result.message else "No output")


async def fork_subagent_example():
    """
    Fork 子 Agent 示例
    
    展示如何使用 Fork 机制创建子 Agent 处理子任务。
    """
    print("\n" + "=" * 60)
    print("Fork Subagent Example")
    print("=" * 60)

    client = OpenAIClient(model="gpt-4")
    fork_manager = ForkSubagentManager(max_concurrent_forks=3)

    # 主 Agent 任务
    main_task = "Analyze the project and delegate subtasks to specialized agents"
    
    # 创建 Fork 任务
    subtasks = [
        "Analyze the CLI module structure",
        "Review the agent system implementation",
        "Check the tool system design",
    ]

    print(f"\nMain task: {main_task}")
    print(f"Creating {len(subtasks)} fork subagents...")

    # 这里简化演示，实际使用需要 AgentExecutor
    for i, subtask in enumerate(subtasks):
        print(f"\nFork {i+1}: {subtask}")
        # 实际使用时:
        # fork_id = fork_manager.spawn_fork(subtask, messages, executor)
        # result = await fork_manager.execute_fork(fork_id, executor, messages)

    print("\nFork subagents would execute in parallel here...")


async def agent_with_streaming():
    """
    带流式输出的 Agent 示例
    
    展示如何在 Agent 执行中使用流式输出。
    """
    print("\n" + "=" * 60)
    print("Agent with Streaming Output")
    print("=" * 60)

    client = OpenAIClient(model="gpt-4")

    from ccmas.agent.run_agent import run_agent_streaming

    messages = [
        UserMessage(content="Explain the benefits of multi-agent systems")
    ]

    # 回调函数
    def on_chunk(chunk: str):
        print(chunk, end="", flush=True)

    def on_tool_call(tool_call):
        print(f"\n[Tool called: {tool_call.function.get('name')}]")

    print("\nAgent response:")
    result = await run_agent_streaming(
        agent=EXPLORER_AGENT,
        messages=messages,
        llm_client=client,
        on_chunk=on_chunk,
        on_tool_call=on_tool_call,
    )

    print(f"\n\nExecution complete!")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")


async def hierarchical_agent_delegation():
    """
    层级 Agent 委派示例
    
    展示如何创建层级结构的 Agent 系统。
    """
    print("\n" + "=" * 60)
    print("Hierarchical Agent Delegation")
    print("=" * 60)

    # 定义主管 Agent
    supervisor_config = AgentConfig(
        model="gpt-4",
        tools=["*"],
        permission_mode=PermissionModeType.DEFAULT,
        system_prompt="""You are a supervisor agent. Your role is to:
1. Understand complex tasks
2. Delegate subtasks to specialized agents
3. Coordinate between agents
4. Synthesize final results

When given a task, break it down and delegate to appropriate specialists.""",
    )

    supervisor = BuiltInAgentDefinition(
        name="supervisor",
        description="Coordinates multiple specialized agents",
        kind=AgentKind.BUILTIN,
        config=supervisor_config,
    )

    client = OpenAIClient()

    # 复杂任务
    complex_task = """
    We need to improve our codebase. Please:
    1. Explore the current structure
    2. Review code quality
    3. Update documentation
    4. Provide a comprehensive improvement plan
    """

    print(f"\nSupervisor Agent: {supervisor.name}")
    print(f"Task: {complex_task}")
    print("\nThe supervisor would:")
    print("  1. Use Explorer Agent to analyze structure")
    print("  2. Use Code Reviewer Agent to check quality")
    print("  3. Use Documentation Agent to update docs")
    print("  4. Synthesize all results into a plan")

    # 实际执行
    messages = [UserMessage(content=complex_task)]
    
    # 这里简化演示
    print("\n[In a full implementation, the supervisor would delegate to sub-agents]")


async def agent_team_coordination():
    """
    Agent 团队协调示例
    
    展示如何协调多个 Agent 作为团队工作。
    """
    print("\n" + "=" * 60)
    print("Agent Team Coordination")
    print("=" * 60)

    # 定义开发团队
    team = {
        "architect": BuiltInAgentDefinition(
            name="architect",
            description="Designs system architecture",
            kind=AgentKind.BUILTIN,
            config=AgentConfig(
                model="gpt-4",
                tools=["read", "search"],
                system_prompt="You are a system architect. Design clean, scalable architectures.",
            ),
        ),
        "developer": BuiltInAgentDefinition(
            name="developer",
            description="Implements features",
            kind=AgentKind.BUILTIN,
            config=AgentConfig(
                model="gpt-4",
                tools=["read", "write", "bash"],
                permission_mode=PermissionModeType.ACCEPT_EDITS,
                system_prompt="You are a developer. Write clean, efficient code.",
            ),
        ),
        "tester": BuiltInAgentDefinition(
            name="tester",
            description="Tests implementations",
            kind=AgentKind.BUILTIN,
            config=AgentConfig(
                model="gpt-4",
                tools=["read", "bash", "write"],
                system_prompt="You are a QA engineer. Write comprehensive tests.",
            ),
        ),
    }

    print("\nDevelopment Team:")
    for role, agent in team.items():
        print(f"  - {role}: {agent.description}")

    # 模拟开发流程
    project_task = "Create a user authentication system"
    
    print(f"\nProject: {project_task}")
    print("\nWorkflow:")
    print("  1. Architect designs the auth system")
    print("  2. Developer implements the design")
    print("  3. Tester writes and runs tests")
    print("  4. Team reviews and iterates")


async def main():
    """主函数：运行所有多 Agent 示例"""
    print("=" * 60)
    print("CCMAS Multi-Agent Examples")
    print("=" * 60)

    examples = [
        ("Parallel Agent Execution", parallel_agent_execution),
        ("Sequential Agent Pipeline", sequential_agent_pipeline),
        ("Fork Subagent", fork_subagent_example),
        ("Agent with Streaming", agent_with_streaming),
        ("Hierarchical Delegation", hierarchical_agent_delegation),
        ("Team Coordination", agent_team_coordination),
    ]

    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            print(f"\nError in {name}: {e}")

    print("\n" + "=" * 60)
    print("All multi-agent examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
