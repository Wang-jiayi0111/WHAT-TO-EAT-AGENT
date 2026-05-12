# E2E 单用例报告：`multi_turn_059`

- **场景分类**：`multi_turn`
- **来源**：`recipe_adopt.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 这几道面食我都看了碳水有点高还在纠结 | [轮2] 我想通了，今晚主食就用葱油拌面，帮我找这道菜"
  ├── 意图识别：主意图 期望 `recipe_adopt` · 实际 `recipe_search` ✗；多意图 期望去重=['recipe_adopt', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search']` 召回=0.50 ✗
  ├── 槽位提取：recipe_adoption=?, recipe_name≈匹配 ✗
  ├── 检索调用：候选标题线索 1 条，金标最佳名次=1 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「以下为「葱油拌面」的用料清单（来自本地菜谱解析）：    · 干面条：80 g   · 小葱：100 g   · 食用油：100 ml   · 生抽：60 ml   · 老抽：20 ml   · 白糖：15 g  以下为「葱油拌面」的烹饪步…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_adopt` | `recipe_search` |
| intents（多意图子集召回） | `['recipe_adopt', 'recipe_search']` | `['recipe_search']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_葱油拌面']` | `recipe_id_葱油拌面:命中@1` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.902988`

- **检索层 §5.1**：aggregate=`1.0000`
- **生成层 §5.2**：aggregate=`0.9250`
- **对话层 §5.3**：aggregate=`0.7765`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=61361.748 tokens=None mcp≈2

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
