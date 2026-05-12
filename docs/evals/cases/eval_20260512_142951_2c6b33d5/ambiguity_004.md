# E2E 单用例报告：`ambiguity_004`

- **场景分类**：`ambiguity`
- **来源**：`recipe_search.json`

## §5.5 业务链路树

```text
用户输入："来个网上很火的那个茄子做法"
  ├── 意图识别：主意图 期望 `recipe_search` · 实际 `recipe_search` ✓；多意图 期望去重=['recipe_search'] ⊆ 实际（顺序无关）`['recipe_search']` 召回=1.00 ✓
  ├── 槽位提取：recipe_query=? ✗
  ├── 检索调用：候选标题线索 6 条，金标最佳名次=2 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「我找到了以下几个相关菜谱（按检索相关性排序），请问您想做哪一个？    1. 烤茄子   2. 鱼香茄子   3. 炒茄子   4. 红烧茄子   5. 茄子炖土豆   6. 蒲烧茄子  请回复序号数字（如 1）或菜名即可。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_search` | `recipe_search` |
| intents（多意图子集召回） | `['recipe_search']` | `['recipe_search']` |
| needs_clarification | `True` | `False` |
| golden_recipe_ids | `['recipe_id_鱼香茄子']` | `recipe_id_鱼香茄子:命中@2` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.760167`

- **检索层 §5.1**：aggregate=`0.5500`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=16902.185 tokens=None mcp≈1

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
