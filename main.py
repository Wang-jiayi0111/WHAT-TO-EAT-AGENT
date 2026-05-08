# # F:\WHAT-TO-EAT-AGENT\main.py
# import asyncio
# import sys
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent))

# from src.agent.workflow import create_agent, run_turn

# async def main():
#     agent = create_agent()
#     while True:
#         user_input = input("你：").strip()
#         if not user_input:
#             continue
#         reply = await run_turn(agent, user_input)
#         print(f"助手：{reply}\n")

# if __name__ == "__main__":
#     asyncio.run(main())

import asyncio
import logging
import sys
import uuid

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.status import Status

from src.agent.state import empty_agent_slices
from src.agent.workflow import create_agent, run_turn
from src.libs.base.config_startup_check import run_startup_configuration_check
from src.libs.base.settings import Settings
from src.observability.runtime_context import bind_invocation_session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 1. 导入你编译好的图（假设在 workflow.py 中有一个 compiled_graph 变量或 get_app 函数）
from src.agent.workflow import build_graph 

console = Console()

# 节点状态提示语映射
STATUS_MAP = {
    "logistics": "🥦 正在为您打理厨房库存...",
    "researcher": "🍳 正在翻阅海量菜谱...",
    "clarify_resolver": "🤔 正在理解您的选择...",
    "generator": "✨ 正在生成最终回复..."
}

async def terminal_chat(agent):
    """终端对话主循环"""
    console.print("[bold cyan]欢迎使用“今天吃什么”膳食助手！(输入 'quit' 退出)[/bold cyan]")
    console.print("-" * 50)
    
    # 为当前对话生成一个唯一的 thread_id（用于记忆持久化）
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        # 1. 获取用户输入
        user_input = console.input("[bold green]您: [/bold green]")
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            console.print("[bold yellow]期待下次为您服务，再见！[/bold yellow]")
            break
            
        if not user_input.strip():
            continue

        input_state = {
            **empty_agent_slices(),
            "messages": [HumanMessage(content=user_input)],
            "active_user_id": "default_user",
        }

        final_reply = ""

        current = await agent.aget_state(config)
        print(f"🔍 [astream前] checkpointer task_stack: {current.values.get('task_stack', [])}")
        print(f"🔍 [astream前] checkpointer 所有keys: {list(current.values.keys())}")


        # 2. 开启带有呼吸灯动画的加载框
        with console.status("[bold blue]🤖 助手正在思考...") as status:
            try:
                with bind_invocation_session(thread_id):
                    async for event in agent.astream(
                        input_state, config, stream_mode="updates"
                    ):
                        for node_name, state_updates in event.items():
                            if node_name in STATUS_MAP:
                                status.update(
                                    f"[bold yellow]{STATUS_MAP[node_name]}"
                                )
                            if node_name == "generator":
                                messages = state_updates.get("messages", [])
                                if messages:
                                    final_reply = messages[-1].content
            except Exception as e:
                final_reply = f"抱歉，系统开小差了：{e}"

        # 4. 动画框自动消失，打印最终结果
        console.print(f"[bold cyan]助手:[/bold cyan] {final_reply}\n")


async def main():
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s: %(message)s",
        )
    if not run_startup_configuration_check(Settings()):
        console.print("[bold red]配置自检未通过，进程退出。请查看上方日志。[/bold red]")
        sys.exit(1)

    agent = create_agent()
    await terminal_chat(agent)

if __name__ == "__main__":
    # 因为包含了 async 异步函数，所以必须用 asyncio.run 来启动整个程序
    asyncio.run(main())