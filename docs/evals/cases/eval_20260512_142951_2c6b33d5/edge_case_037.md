# E2E 单用例报告：`edge_case_037`

- **场景分类**：`edge_case`
- **来源**：`general_chat.json`

## §5.5 业务链路树

```text
用户输入："今天下班好累啊随便聊聊吃啥能让我开心点"
  ├── 意图识别：主意图 期望 `general_chat` · 实际 `dietary_advice` ✗；多意图 期望去重=['general_chat'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=0.00 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「累了一天确实需要好好犒劳下自己呢！食物对心情的影响还是挺大的，比如巧克力能够促进大脑释放让人感觉愉快的化学物质，适量吃点黑巧克力既能满足口感又能提升心情。还有香蕉，它富含维生素B6，可以帮助身体合成血清素，也是一种能让人感到快乐的物质。当然…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `general_chat` | `dietary_advice` |
| intents（多意图子集召回） | `['general_chat']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.7065`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7065`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=18910.171 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
