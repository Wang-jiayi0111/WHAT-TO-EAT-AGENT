# E2E 单用例报告：`nutrition_query_005`

- **场景分类**：`nutrition_query`
- **来源**：`recipe_search.json`

## §5.5 业务链路树

```text
用户输入："减脂期午餐想吃点饱腹又低脂的菜谱，有什么推荐"
  ├── 意图识别：主意图 期望 `recipe_search` · 实际 `recipe_search` ✓；多意图 期望去重=['recipe_search', 'dietary_advice'] ⊆ 实际（顺序无关）`['recipe_search', 'dietary_advice']` 召回=1.00 ✓
  ├── 槽位提取：recipe_query 期望含 `减脂午餐低脂饱腹` 实际 `饱腹且低脂的午餐` ✗
  ├── 检索调用：候选标题线索 14 条，金标最佳名次=1 ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「我找到了以下几个相关菜谱（按检索相关性排序），请问您想做哪一个？    1. 麻辣减脂荞麦面   2. 凉皮   3. 上汤娃娃菜   4. 瘦肉土豆片   5. 凉拌鸡丝   6. 紫菜蛋花汤  请回复序号数字（如 1）或菜名即可。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_search` | `recipe_search` |
| intents（多意图子集召回） | `['recipe_search', 'dietary_advice']` | `['recipe_search', 'dietary_advice']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_麻辣减脂荞麦面', 'recipe_id_瘦肉土豆片', 'recipe_id_凉拌鸡丝', 'recipe_id_上汤娃娃菜']` | `recipe_id_麻辣减脂荞麦面:命中@1; recipe_id_瘦肉土豆片:命中@4; recipe_id_凉拌鸡丝:命中@5; recipe_id_上汤娃娃菜:命中@3` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.969426`

- **检索层 §5.1**：aggregate=`1.0000`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9365`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=19036.703 tokens=None mcp≈1

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
