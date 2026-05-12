# E2E 单用例报告：`nutrition_query_020`

- **场景分类**：`nutrition_query`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："感冒了嗓子疼饮食上要注意什么能吃点啥缓解"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `dietary_advice` ✓；多意图 期望去重=['dietary_advice', 'recipe_search'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=0.50 ✗
  ├── 槽位提取：diet_topic 期望含 `感冒咽痛饮食` 实际 `感冒 嗓子疼`, ingredients=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「感冒嗓子疼的时候，饮食上可以注意以下几点来帮助缓解不适：  1. **多喝水**：保持充足的水分可以帮助稀释喉咙中的分泌物，减轻疼痛感。温开水、淡盐水或是蜂蜜柠檬水都是不错的选择。 2. **温和易吞咽的食物**：选择软烂、容易吞咽的食物，…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `dietary_advice` | `dietary_advice` |
| intents（多意图子集召回） | `['dietary_advice', 'recipe_search']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.8665`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.8665`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=21905.369 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
