import asyncio
import pytest
from pathlib import Path
import sys
import logging

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent 

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.agent.nodes.researcher import researcher_node
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@pytest.mark.asyncio
async def test_run_integration():
    print("🚀 开始 researcher.py 完整功能测试...")

    # 1. 构造初始状态 (模拟用户想要做梅菜扣肉)
    state = {
        "messages": [HumanMessage(content="梅菜扣肉怎么做")],
        "task_stack": [],
        "active_user_id": "test_user_001",
        "logistics_buffer": {
            "extracted_entities": {"recipe_name": "梅菜扣肉"},
            "selected_recipe_title": "梅菜扣肉",
            "recipe_requirements": [],
            "recipe_candidates": []
        },
        "expert_payloads": {} 
    }

    try:
        # 2. 运行节点逻辑
        # 此时会触发：启动 server.py -> search_recipes -> (可选) get_recipe_details -> LLM 解析
        print("--- 正在调用 researcher_node ---")
        new_state = await researcher_node(state)
        
        # 3. 验证结果
        print("\n✅ 测试完成！执行结果如下：")
        
        # 检查是否成功锁定并解析了食材
        lb = new_state.get("logistics_buffer", {})
        if lb.get("recipe_requirements"):
            print(f"📍 状态：自动锁定成功")
            print(f"🍴 确定的菜谱 ID: {lb.get('selected_recipe_id')}")
            print(f"📦 提取到的食材数量: {len(lb['recipe_requirements'])}")
        
        # 检查是否进入了歧义处理逻辑
        elif "TASK_CLARIFY" in new_state.get("task_stack", []):
            print(f"📍 状态：进入歧义处理模式")
            candidates = lb.get("recipe_candidates", [])
            print(f"📚 候选菜谱列表: {', '.join(candidates)}")

        # 打印专家交付区数据
        print(f"🧠 专家数据状态: {new_state.get('expert_payloads', {}).get('status')}")

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_run_integration())