# E2E 单用例报告：`nutrition_query_022`

- **场景分类**：`nutrition_query`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："我每天健身一小时想减脂，碳水蛋白脂肪大概怎么分配比较现实"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `dietary_advice` ✓；多意图 期望去重=['dietary_advice'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=1.00 ✓
  ├── 槽位提取：diet_topic≈匹配 ✓
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「很高兴你选择了健康的方式来达到减脂的目的！对于想要通过健身和饮食控制来减脂的朋友来说，合理的营养分配是非常重要的。一般来说，推荐的碳水化合物、蛋白质与脂肪的比例可以是40%:30%:30%，但这需要根据个人的具体情况（如年龄、性别、体重、活…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `dietary_advice` | `dietary_advice` |
| intents（多意图子集召回） | `['dietary_advice']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9865`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=24349.541 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
