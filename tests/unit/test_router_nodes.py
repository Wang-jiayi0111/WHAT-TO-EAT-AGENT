import pytest
import json
from langchain_core.messages import HumanMessage
from src.agent.nodes.router import router_node
from src.agent.state import AgentState

# 定义测试数据集：覆盖标准、复合、模糊、指代消歧等场景
TEST_CASES = [
    {
        "name": "标准单意图 - 搜菜谱",
        "input": "我想学做红烧肉",
        "expected_intent": "recipe_search"
    },
    {
        "name": "复合意图 - 搜索+库存",
        "input": "今晚想吃西红柿炒蛋，帮我看看鸡蛋还够吗？",
        "expected_intent": "recipe_search" # 主意图
    },
    {
        "name": "指代消歧 - 结合历史背景",
        "input": "那个还有吗？",
        "history": "用户刚刚询问过‘冰箱里还有没有牛肉’",
        "expected_intent": "inventory_check"
    },
    {
        "name": "偏好录入 - 成员禁忌",
        "input": "记一下，我女儿对蚕豆过敏",
        "expected_intent": "profile_sync"
    },
    {
        "name": "低置信度 - 模糊输入",
        "input": "额... 你好",
        "expected_intent": "general_chat"
    }
]

@pytest.mark.parametrize("case", TEST_CASES)
def test_router_logic_transparency(case):
    """
    测试路由节点并打印完整的 LLM 推理过程和 State 变化
    """
    print(f"\n\n{'='*20} 测试用例: {case['name']} {'='*20}")
    
    # 1. 构造初始 State
    state: AgentState = {
        "messages": [HumanMessage(content=case["input"])],
        "active_user_id": "user_dev_01",
        "memory_summary": case.get("history", "无历史对话"),
        "task_stack": [],
        "logistics_buffer": {}
    }

    # 2. 执行节点逻辑
    # 此时内部会调用 LLMFactory 并获取结构化输出
    try:
        output = router_node(state)
        
        # 3. 打印可视化结果，方便调试
        print(f"用户输入: {case['input']}")
        print(f"历史背景: {state['memory_summary']}")
        print("-" * 50)
        
        # 核心：显示 LLM 的原始思考过程
        # 注意：这些数据是从我们定义的 logistics_buffer 中提取的
        reasoning = output.get("logistics_buffer", {}).get("router_reasoning", "N/A")
        print(f"【LLM 思考推理】: \n{reasoning}")
        
        print("-" * 50)
        # 显示路由后的 State 关键字段
        print(f"【识别意图】: {output.get('current_intent')}")
        print(f"【生成任务栈】: {output.get('task_stack')}")
        print(f"【提取实体】: {json.dumps(output.get('logistics_buffer', {}).get('extracted_entities'), ensure_ascii=False, indent=2)}")
        
        # 4. 基础断言
        if case["expected_intent"] != "general_chat": # 忽略闲聊的强制匹配
             assert case["expected_intent"] in output.get("current_intent") or \
                    case["expected_intent"] in str(output.get("task_stack"))

    except Exception as e:
        pytest.fail(f"路由节点执行崩溃: {e}")