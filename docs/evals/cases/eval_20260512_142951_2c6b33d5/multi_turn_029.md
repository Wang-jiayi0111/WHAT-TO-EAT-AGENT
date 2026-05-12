# E2E 单用例报告：`multi_turn_029`

- **场景分类**：`multi_turn`
- **来源**：`shopping_list.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 今晚做水煮鱼 | [轮2] 告诉我除了底料和鱼以外还需要采购哪些配料一并列购物单"
  ├── 意图识别：主意图 期望 `shopping_list` · 实际 `recipe_search` ✗；多意图 期望去重=['shopping_list', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search', 'shopping_list']` 召回=1.00 ✓
  ├── 槽位提取：list_action≈匹配 ✓
  ├── 检索调用：候选标题线索 1 条，金标最佳名次=1 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「已按**最新库存**与菜谱用料重新计算缺口，待购清单如下：    · 巴沙鱼：500.0 g   · 蔬菜（比如土豆片/豆芽/花菜/生菜/……）：400.0 g   · 红油豆瓣酱：40.0 g   · 藤椒油：10.0 ml   · 菜籽…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `shopping_list` | `recipe_search` |
| intents（多意图子集召回） | `['shopping_list', 'recipe_search']` | `['recipe_search', 'shopping_list']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_水煮鱼']` | `recipe_id_水煮鱼:命中@1` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.921125`

- **检索层 §5.1**：aggregate=`1.0000`
- **生成层 §5.2**：aggregate=`0.8375`
- **对话层 §5.3**：aggregate=`0.8600`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=97038.625 tokens=None mcp≈2

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
