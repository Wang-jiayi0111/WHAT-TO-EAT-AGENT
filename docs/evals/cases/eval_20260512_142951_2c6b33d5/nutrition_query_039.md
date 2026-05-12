# E2E 单用例报告：`nutrition_query_039`

- **场景分类**：`nutrition_query`
- **来源**：`general_chat.json`

## §5.5 业务链路树

```text
用户输入："我朋友都说我做饭太咸，但我吃着刚好，这算口味重吗？"
  ├── 意图识别：主意图 期望 `general_chat` · 实际 `dietary_advice` ✗；多意图 期望去重=['general_chat', 'dietary_advice'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=0.50 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「这可能意味着你的口味偏重一些哦。其实，减少盐分摄入对健康很有好处，可以帮助降低高血压的风险。你可以试着逐渐减少做菜时放的盐量，或者用其他调味品来替代，比如醋、柠檬汁或者是香草等自然香料，这样既能保证食物美味，又能更加健康。记得多听听朋友的意…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `general_chat` | `dietary_advice` |
| intents（多意图子集召回） | `['general_chat', 'dietary_advice']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.79`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7900`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=24050.294 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
