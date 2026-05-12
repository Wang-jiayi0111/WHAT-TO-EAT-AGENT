# E2E 单用例报告：`inventory_014`

- **场景分类**：`inventory`
- **来源**：`inventory_add.json`

## §5.5 业务链路树

```text
用户输入："菜场买了三百克五花肉入库"
  ├── 意图识别：主意图 期望 `inventory_add` · 实际 `inventory_add` ✓；多意图 期望去重=['inventory_add'] ⊆ 实际（顺序无关）`['inventory_add']` 召回=1.00 ✓
  ├── 槽位提取：restock_items 期望含 `[{'name': '五花肉', 'amount': 300, 'unit': 'g', 'merge_mode': 'add'}]` 实际 `['{"name": "五花肉", "amount": 300, "unit": "克"}']` ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「没能从您的话里确定买了哪些食材、各多少量（需带单位）。请再说具体一点，例如「买了鸡蛋 12 个」。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `inventory_add` | `inventory_add` |
| intents（多意图子集召回） | `['inventory_add']` | `['inventory_add']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9365`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9365`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=8694.919 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
