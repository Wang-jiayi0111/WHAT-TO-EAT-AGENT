# E2E 单用例报告：`recipe_query_070`

- **场景分类**：`recipe_query`
- **来源**：`user_clarify.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 想吃红烧肉一类家常菜，我还没想好偏甜还是偏咸 | [轮2] 那就家常红烧偏咸鲜口吧，不要太甜"
  ├── 意图识别：主意图 期望 `user_clarify` · 实际 `profile_sync` ✗；多意图 期望去重=['user_clarify', 'recipe_search'] ⊆ 实际（顺序无关）`['profile_sync', 'recipe_search']` 召回=0.50 ✗
  ├── 槽位提取：recipe_query 期望含 `红烧咸鲜不太甜` 实际 `红烧肉一类家常菜` ✗
  ├── 检索调用：候选标题线索 14 条，金标最佳名次=3 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「抱歉，没能识别您的选择。请回复列表中的序号（1～6），或直接输入菜名（可输入部分关键词）。  我找到了以下几个相关菜谱（按检索相关性排序），请问您想做哪一个？    1. 辣椒炒肉   2. 蒜苔炒肉末   3. 简易红烧肉   4. 鱼香…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `user_clarify` | `profile_sync` |
| intents（多意图子集召回） | `['user_clarify', 'recipe_search']` | `['profile_sync', 'recipe_search']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_简易红烧肉']` | `recipe_id_简易红烧肉:命中@3` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.621093`

- **检索层 §5.1**：aggregate=`0.5000`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7515`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=17994.291 tokens=None mcp≈1

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
