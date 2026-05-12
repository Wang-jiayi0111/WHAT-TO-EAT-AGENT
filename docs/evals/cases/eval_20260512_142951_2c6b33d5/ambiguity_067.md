# E2E 单用例报告：`ambiguity_067`

- **场景分类**：`ambiguity`
- **来源**：`user_clarify.json`

## §5.5 业务链路树

```text
用户输入："我要第二个酸辣口味的版本不是酸甜那个"
  ├── 意图识别：主意图 期望 `user_clarify` · 实际 `recipe_adopt` ✗；多意图 期望去重=['user_clarify'] ⊆ 实际（顺序无关）`['recipe_adopt']` 召回=0.00 ✗
  ├── 槽位提取：recipe_name=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「抱歉，我没有找到合适的菜谱，请换个关键词再试试？」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `user_clarify` | `recipe_adopt` |
| intents（多意图子集召回） | `['user_clarify']` | `['recipe_adopt']` |
| needs_clarification | `False` | `True` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.4065`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.4065`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=10617.15 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
