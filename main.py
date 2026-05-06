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
from rich.console import Console
from rich.status import Status
import uuid
import logging
from src.agent.workflow import create_agent, run_turn
from src.agent.state import empty_agent_slices

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 1. 导入你编译好的图（假设在 workflow.py 中有一个 compiled_graph 变量或 get_app 函数）
from src.agent.workflow import build_graph 

console = Console()

# 节点状态提示语映射
STATUS_MAP = {
    "logistics": "🥦 正在为您打理厨房库存...",
    "researcher": "🍳 正在翻阅海量菜谱...",
    "memory_keeper": "🧠 正在匹配您的饮食偏好...",
    "clarify_resolver": "🤔 正在理解您的选择...",
    "generator": "✨ 正在生成最终回复..."
}

async def terminal_chat(agent):
    """终端对话主循环"""
    console.print("[bold cyan]欢迎使用“今天才吃什么”膳食助手！(输入 'quit' 退出)[/bold cyan]")
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
            "messages": [("user", user_input)],
        }

        final_reply = ""

        current = await agent.aget_state(config)
        print(f"🔍 [astream前] checkpointer task_stack: {current.values.get('task_stack', [])}")
        print(f"🔍 [astream前] checkpointer 所有keys: {list(current.values.keys())}")


        # 2. 开启带有呼吸灯动画的加载框
        with console.status("[bold blue]🤖 助手正在思考...") as status:
            try:
                # 3. 流式监听 LangGraph 的节点运转
                async for event in agent.astream(input_state, config, stream_mode="updates"):
                    for node_name, state_updates in event.items():
                        
                        # 如果跑到了已知节点，更新控制台的动画文字
                        if node_name in STATUS_MAP:
                            status.update(f"[bold yellow]{STATUS_MAP[node_name]}")
                        
                        # 如果跑到了 generator 节点，提取准备发给用户的文字
                        if node_name == "generator":
                            messages = state_updates.get("messages", [])
                            if messages:
                                final_reply = messages[-1].content
            except Exception as e:
                final_reply = f"抱歉，系统开小差了：{e}"

        # 4. 动画框自动消失，打印最终结果
        console.print(f"[bold cyan]助手:[/bold cyan] {final_reply}\n")


async def main():
    # 初始化你的图模型
    agent = create_agent()
    
    # 启动终端对话
    await terminal_chat(agent)

if __name__ == "__main__":
    # 因为包含了 async 异步函数，所以必须用 asyncio.run 来启动整个程序
    asyncio.run(main())