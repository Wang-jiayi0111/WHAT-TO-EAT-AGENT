# E2E 单用例报告：`multi_turn_006`

- **场景分类**：`multi_turn`
- **来源**：`recipe_search.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 我不吃羊肉和膻味重的肉类，记住了 | [轮2] 帮我推荐一道暖身的炖菜菜谱作为晚餐"
  ├── 意图识别：主意图 期望 `recipe_search` · 实际 `recipe_search` ✓；多意图 期望去重=['recipe_search', 'profile_sync'] ⊆ 实际（顺序无关）`['recipe_search']` 召回=0.50 ✗
  ├── 槽位提取：recipe_query 期望含 `暖身炖菜` 实际 `暖身的炖菜`, ingredients=? ✗
  ├── 检索调用：候选标题线索 0 条 ✗
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「抱歉，我没有找到合适的菜谱，请换个关键词再试试？」✗；检索硬失败封顶
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_search` | `recipe_search` |
| intents（多意图子集召回） | `['recipe_search', 'profile_sync']` | `['recipe_search']` |
| needs_clarification | `False` | `True` |
| golden_recipe_ids | `['recipe_id_广式萝卜牛腩', 'recipe_id_西红柿土豆炖牛肉', 'recipe_id_鲤鱼炖白菜', 'recipe_id_鳊鱼炖豆腐']` | `recipe_id_广式萝卜牛腩:未命中; recipe_id_西红柿土豆炖牛肉:未命中; recipe_id_鲤鱼炖白菜:未命中; recipe_id_鳊鱼炖豆腐:未命中` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.270833`（检索硬失败封顶）

- **检索层 §5.1**：aggregate=`0.0000`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.5625`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=17096.414 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
