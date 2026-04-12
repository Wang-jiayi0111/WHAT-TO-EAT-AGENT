"""
对话窗口 + 语义压缩测试

测试场景：
1. 窗口未满 - 不触发压缩
2. 窗口已满 - 触发压缩，旧消息被裁剪
3. 压缩内容正确 - summary 包含关键信息
4. 多轮累积压缩 - summary 与新消息正确融合
5. 压缩后上下文构建 - build_context_messages 结构正确
6. 节点集成 - conversation_memory_node 正确更新 state
"""
import asyncio
import sys
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.nodes.conversation_memory import (
    ConversationMemoryManager,
    conversation_memory_node,
    WINDOW_SIZE,
    COMPRESS_TRIGGER,
)


# ── 工具函数 ──────────────────────────────────────────────

def make_messages(n: int) -> list:
    """生成 n 轮对话消息（每轮 1 条 Human + 1 条 AI = 2 条）。"""
    messages = []
    topics = [
        ("我对花生过敏，请帮我推荐菜谱", "好的，我会避开花生相关食材为您推荐。"),
        ("我想吃红烧肉", "为您找到了几个红烧肉菜谱，评分最高的是南派红烧肉。"),
        ("我最近在减脂，热量不要太高", "明白，我会优先推荐低脂高蛋白的菜谱。"),
        ("有没有适合快手的菜", "推荐番茄炒蛋，15分钟内可以完成。"),
        ("我不喜欢香菜", "已记录，后续推荐会避开含香菜的菜谱。"),
        ("今天想吃点辣的", "为您推荐了水煮鱼和辣子鸡，都是经典川菜。"),
        ("帮我看看这道菜的做法", "这道菜需要先将食材切好，然后热锅凉油..."),
        ("下一步怎么做", "下一步需要将锅预热至中火，加入葱姜爆香。"),
    ]
    for i in range(n):
        topic = topics[i % len(topics)]
        messages.append(HumanMessage(content=topic[0]))
        messages.append(AIMessage(content=topic[1]))
    return messages


def make_state(messages: list, summary: str = "") -> dict:
    return {
        "messages": messages,
        "conversation_summary": summary,
        "active_user_id": "test_user_compress",
        "logistics_buffer": {},
        "task_stack": [],
        "expert_payloads": {},
    }


# ════════════════════════════════════════════════════════════
# Part 1：单元测试（不调用 LLM）
# ════════════════════════════════════════════════════════════

def test_no_compression_when_below_trigger():
    """窗口未满时不触发压缩。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(COMPRESS_TRIGGER // 2)  # 远低于阈值
    assert manager.needs_compression(messages) is False
    print(f"✅ 消息数 {len(messages)} < 触发阈值 {COMPRESS_TRIGGER}，不触发压缩")


def test_compression_triggered_when_above_threshold():
    """消息数超过阈值时 needs_compression 返回 True。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(COMPRESS_TRIGGER + 1)
    assert manager.needs_compression(messages) is True
    print(f"✅ 消息数 {len(messages)} > 触发阈值 {COMPRESS_TRIGGER}，触发压缩")


def test_window_size_after_trim():
    """压缩后保留的消息数应等于 WINDOW_SIZE。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(COMPRESS_TRIGGER + 2)
    trimmed = messages[-WINDOW_SIZE:]
    assert len(trimmed) == WINDOW_SIZE
    print(f"✅ 裁剪后消息数: {len(trimmed)} == WINDOW_SIZE({WINDOW_SIZE})")


def test_messages_to_compress_are_oldest():
    """被压缩的消息应该是最早的那些，不是最新的。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(COMPRESS_TRIGGER + 1)
    to_compress = messages[:-WINDOW_SIZE]
    kept = messages[-WINDOW_SIZE:]

    # 最早的消息在 to_compress 里
    assert to_compress[0] == messages[0]
    # 最新的消息在 kept 里
    assert kept[-1] == messages[-1]
    print(f"✅ 压缩对象: 前 {len(to_compress)} 条（最旧），保留后 {len(kept)} 条（最新）")


def test_build_context_messages_structure():
    """build_context_messages 应正确组装 system + summary + messages。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(3)
    summary = "用户对花生过敏，偏好清淡菜肴。"
    system_prompt = "你是一个智能膳食助手。"

    context = manager.build_context_messages(messages, summary, system_prompt)

    # 第一条应该是 system prompt
    assert isinstance(context[0], SystemMessage)
    assert "智能膳食助手" in context[0].content

    # 第二条应该是 summary
    assert isinstance(context[1], SystemMessage)
    assert summary in context[1].content

    # 剩余是原始消息
    assert context[2:] == messages
    print(f"✅ 上下文结构正确: [SystemPrompt] + [Summary] + {len(messages)} 条原始消息")


def test_build_context_without_summary():
    """没有 summary 时不应插入 summary 消息。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = make_messages(2)

    context = manager.build_context_messages(messages, summary="", system_prompt="系统提示")

    assert len(context) == 1 + len(messages)  # 只有 system + messages
    assert isinstance(context[0], SystemMessage)
    assert context[1:] == messages
    print("✅ 无 summary 时上下文结构正确: [SystemPrompt] + 原始消息")


def test_format_messages_for_compression():
    """消息格式化应正确区分用户和助手。"""
    manager = ConversationMemoryManager.__new__(ConversationMemoryManager)
    messages = [
        HumanMessage(content="我想吃红烧肉"),
        AIMessage(content="为您推荐南派红烧肉"),
    ]
    text = manager._format_messages_for_compression(messages)
    assert "用户：我想吃红烧肉" in text
    assert "助手：为您推荐南派红烧肉" in text
    print(f"✅ 消息格式化正确:\n{text}")


# ════════════════════════════════════════════════════════════
# Part 2：LLM 集成测试（调用真实模型）
# ════════════════════════════════════════════════════════════

async def test_compress_preserves_key_info():
    """
    场景：压缩包含关键偏好信息的对话，summary 应保留这些信息。
    """
    print("\n🧪 场景：压缩后 summary 保留关键信息")
    manager = ConversationMemoryManager()

    messages_to_compress = [
        HumanMessage(content="我对花生过敏，推荐菜谱时一定要避开"),
        AIMessage(content="好的，已记录您的花生过敏信息。"),
        HumanMessage(content="我在减脂，希望菜谱热量不要太高"),
        AIMessage(content="明白，我会优先推荐低脂高蛋白的菜谱。"),
        HumanMessage(content="今天推荐了红烧肉，我觉得很好"),
        AIMessage(content="很高兴您喜欢，下次可以尝试同风格的东坡肉。"),
    ]

    summary = await manager.compress(messages_to_compress, existing_summary="")
    print(f"生成的 summary:\n{summary}")

    # 验证关键信息被保留
    assert any(keyword in summary for keyword in ["花生", "过敏", "allergen"]), \
        "summary 应包含花生过敏信息"
    assert any(keyword in summary for keyword in ["减脂", "低脂", "热量"]), \
        "summary 应包含减脂目标"
    print("✅ 关键信息已保留在 summary 中")
    return summary


async def test_compress_merges_with_existing_summary():
    """
    场景：已有 summary 时，新压缩内容应融合进去，不是简单拼接。
    """
    print("\n🧪 场景：新旧 summary 融合")
    manager = ConversationMemoryManager()

    existing_summary = "用户对花生过敏，正在减脂，已推荐过南派红烧肉。"

    new_messages = [
        HumanMessage(content="我不喜欢香菜，之后别推荐含香菜的菜"),
        AIMessage(content="好的，已记录您不喜欢香菜。"),
        HumanMessage(content="今天想吃辣的"),
        AIMessage(content="为您推荐了水煮鱼，是经典川菜。"),
    ]

    merged_summary = await manager.compress(new_messages, existing_summary=existing_summary)
    print(f"融合后的 summary:\n{merged_summary}")

    # 旧信息应保留
    assert any(keyword in merged_summary for keyword in ["花生", "过敏"]), \
        "旧的过敏信息应被保留"
    # 新信息应加入
    assert any(keyword in merged_summary for keyword in ["香菜"]), \
        "新的香菜禁忌应被加入"
    print("✅ 新旧 summary 融合成功")


async def test_maybe_compress_no_trigger():
    """
    场景：消息未超阈值，maybe_compress 应原样返回，不修改消息。
    """
    print("\n🧪 场景：未超阈值，不触发压缩")
    manager = ConversationMemoryManager()

    messages = make_messages(2)  # 4 条，低于阈值
    trimmed, summary = await manager.maybe_compress(messages, existing_summary="")

    assert trimmed is messages  # 同一个对象，没有创建新列表
    assert summary == ""
    print(f"✅ 消息数 {len(messages)} 未超阈值，原样返回")


async def test_maybe_compress_triggers_and_trims():
    """
    场景：消息超过阈值，触发压缩并裁剪消息列表。
    """
    print("\n🧪 场景：超过阈值，触发压缩")
    manager = ConversationMemoryManager()

    # 构造超过阈值的消息，包含有意义的内容
    messages = [
        HumanMessage(content="我对花生过敏"),
        AIMessage(content="已记录花生过敏。"),
        HumanMessage(content="我在减脂"),
        AIMessage(content="已记录减脂目标。"),
        HumanMessage(content="不喜欢香菜"),
        AIMessage(content="已记录不喜欢香菜。"),
        HumanMessage(content="喜欢辣的"),
        AIMessage(content="已记录偏辣口味。"),
        HumanMessage(content="想要快手菜"),
        AIMessage(content="已记录快手菜偏好。"),
        HumanMessage(content="今天吃什么"),  # 这条会被保留在窗口里
        AIMessage(content="为您推荐番茄炒蛋。"),
    ]
    # 确保超过触发阈值
    assert len(messages) > COMPRESS_TRIGGER

    trimmed, summary = await manager.maybe_compress(messages, existing_summary="")

    assert len(trimmed) == WINDOW_SIZE, f"裁剪后应保留 {WINDOW_SIZE} 条，实际 {len(trimmed)} 条"
    assert len(summary) > 0, "应生成非空 summary"
    assert trimmed[-1] == messages[-1], "最新消息应在窗口内"
    print(f"✅ 压缩触发: 原 {len(messages)} 条 → 保留 {len(trimmed)} 条")
    print(f"✅ 生成 summary ({len(summary)} 字符):\n{summary}")


async def test_conversation_memory_node_no_change():
    """
    场景：消息未超阈值，节点返回空字典（不更新 state）。
    """
    print("\n🧪 场景：节点 - 未超阈值返回空字典")
    messages = make_messages(2)
    state = make_state(messages)

    result = await conversation_memory_node(state)
    assert result == {}, f"未超阈值时节点应返回空字典，实际返回: {result}"
    print("✅ 节点正确返回空字典")


async def test_conversation_memory_node_updates_state():
    """
    场景：消息超过阈值，节点应更新 messages 和 conversation_summary。
    """
    print("\n🧪 场景：节点 - 超阈值更新 state")
    messages = [
        HumanMessage(content="我对花生过敏"),
        AIMessage(content="已记录。"),
        HumanMessage(content="我在减脂"),
        AIMessage(content="已记录。"),
        HumanMessage(content="不喜欢香菜"),
        AIMessage(content="已记录。"),
        HumanMessage(content="喜欢辣的"),
        AIMessage(content="已记录。"),
        HumanMessage(content="想要快手菜"),
        AIMessage(content="已记录。"),
        HumanMessage(content="今天吃什么"),
        AIMessage(content="推荐番茄炒蛋。"),
    ]
    assert len(messages) > COMPRESS_TRIGGER

    state = make_state(messages, summary="")
    result = await conversation_memory_node(state)

    assert "messages" in result, "节点应返回更新后的 messages"
    assert "conversation_summary" in result, "节点应返回更新后的 summary"
    assert len(result["messages"]) == WINDOW_SIZE
    assert len(result["conversation_summary"]) > 0
    print(f"✅ 节点更新 state 成功")
    print(f"   messages: {len(result['messages'])} 条")
    print(f"   summary: {result['conversation_summary'][:100]}...")


# ════════════════════════════════════════════════════════════
# 运行入口
# ════════════════════════════════════════════════════════════

def run_unit_tests():
    print("\n" + "="*50)
    print("📦 单元测试（不调用 LLM）")
    print("="*50)
    test_no_compression_when_below_trigger()
    test_compression_triggered_when_above_threshold()
    test_window_size_after_trim()
    test_messages_to_compress_are_oldest()
    test_build_context_messages_structure()
    test_build_context_without_summary()
    test_format_messages_for_compression()
    print("\n🎉 所有单元测试通过！")


async def run_llm_tests():
    print("\n" + "="*50)
    print("🤖 LLM 集成测试（调用真实模型）")
    print("="*50)

    print("\n--- 压缩保留关键信息 ---")
    await test_compress_preserves_key_info()

    print("\n--- 新旧 summary 融合 ---")
    await test_compress_merges_with_existing_summary()

    print("\n--- 未超阈值不触发 ---")
    await test_maybe_compress_no_trigger()

    print("\n--- 超阈值触发压缩 ---")
    await test_maybe_compress_triggers_and_trims()

    print("\n--- 节点：未超阈值返回空 ---")
    await test_conversation_memory_node_no_change()

    print("\n--- 节点：超阈值更新 state ---")
    await test_conversation_memory_node_updates_state()

    print("\n🎉 所有 LLM 集成测试完成！")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["unit", "llm", "all"],
        default="unit",
        help="unit=只测逻辑层, llm=只测LLM集成, all=全部"
    )
    args = parser.parse_args()

    async def main():
        if args.mode in ("unit", "all"):
            run_unit_tests()
        if args.mode in ("llm", "all"):
            await run_llm_tests()

    asyncio.run(main())