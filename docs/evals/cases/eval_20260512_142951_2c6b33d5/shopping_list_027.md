# E2E 单用例报告：`shopping_list_027`

- **场景分类**：`shopping_list`
- **来源**：`shopping_list.json`

## §5.5 业务链路树

```text
用户输入："我改做糖醋里脊了，按新菜谱重新算一遍要买什么"
  ├── 意图识别：主意图 期望 `shopping_list` · 实际 `recipe_search` ✗；多意图 期望去重=['shopping_list', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search', 'shopping_list']` 召回=1.00 ✓
  ├── 槽位提取：list_action=? ✗
  ├── 检索调用：候选标题线索 2 条，金标最佳名次=1 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「已按**最新库存**与菜谱用料重新计算缺口，待购清单如下：    · 清水：50.0 ml   · 生抽：40.0 ml   · 白糖：30.0 g   · 白醋：20.0 ml   · 料酒：10.0 ml  以下为「糖醋里脊」的用料清单…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `shopping_list` | `recipe_search` |
| intents（多意图子集召回） | `['shopping_list', 'recipe_search']` | `['recipe_search', 'shopping_list']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_糖醋里脊']` | `recipe_id_糖醋里脊:命中@1` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.894125`

- **检索层 §5.1**：aggregate=`1.0000`
- **生成层 §5.2**：aggregate=`0.7375`
- **对话层 §5.3**：aggregate=`0.8600`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=37263.048 tokens=None mcp≈2

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
