# E2E 单用例报告：`inventory_010`

- **场景分类**：`inventory`
- **来源**：`inventory_check.json`

## §5.5 业务链路树

```text
用户输入："想做咖喱饭，土豆洋葱胡萝卜和鸡胸肉家里都齐吗"
  ├── 意图识别：主意图 期望 `inventory_check` · 实际 `recipe_search` ✗；多意图 期望去重=['inventory_check', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search', 'inventory_check']` 召回=1.00 ✓
  ├── 槽位提取：inventory_query_targets 期望含 `['土豆', '洋葱', '胡萝卜', '鸡胸肉']` 实际 `['土豆', '洋葱', '胡萝卜', '鸡胸肉']` ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「您的厨房库存目前是空的，还没有添加任何食材。  菜谱检索服务暂时不可用，我无法从本地菜谱库拉取结果。请稍后再试；您也可以先说想吃的口味或食材，我再给您一些不依赖检索的建议。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `inventory_check` | `recipe_search` |
| intents（多意图子集召回） | `['inventory_check', 'recipe_search']` | `['recipe_search', 'inventory_check']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.7965`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7965`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=17270.284 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
