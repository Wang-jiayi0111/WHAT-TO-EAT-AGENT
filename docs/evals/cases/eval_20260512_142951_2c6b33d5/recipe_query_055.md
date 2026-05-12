# E2E 单用例报告：`recipe_query_055`

- **场景分类**：`recipe_query`
- **来源**：`recipe_adopt.json`

## §5.5 业务链路树

```text
用户输入："就选糖醋排骨了，我今晚就做这个，帮我找这道菜"
  ├── 意图识别：主意图 期望 `recipe_adopt` · 实际 `recipe_search` ✗；多意图 期望去重=['recipe_adopt', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search', 'recipe_adopt']` 召回=1.00 ✓
  ├── 槽位提取：recipe_adoption≈匹配, recipe_name≈匹配 ✓
  ├── 检索调用：候选标题线索 1 条，金标最佳名次=1 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的呀，糖醋排骨真是个好选择，酸甜可口，特别下饭。下面给你分享一个简单的做法：  ### 材料 - 排骨 500克 - 生姜几片 - 大葱一根（切段） - 白芝麻少许（装饰用）  ### 调料 - 酱油 1大勺 - 米醋或白醋 4大勺 - …」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_adopt` | `recipe_search` |
| intents（多意图子集召回） | `['recipe_adopt', 'recipe_search']` | `['recipe_search', 'recipe_adopt']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_糖醋排骨']` | `recipe_id_糖醋排骨:命中@1` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.8973`

- **检索层 §5.1**：aggregate=`1.0000`
- **生成层 §5.2**：aggregate=`0.8375`
- **对话层 §5.3**：aggregate=`0.8465`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=75023.112 tokens=None mcp≈2

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
