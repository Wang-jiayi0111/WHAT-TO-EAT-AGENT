# E2E 单用例报告：`nutrition_query_019`

- **场景分类**：`nutrition_query`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："糖尿病患者喝汤要不要撇浮油，有什么原则"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `dietary_advice` ✓；多意图 期望去重=['dietary_advice'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=1.00 ✓
  ├── 槽位提取：diet_topic 期望含 `糖尿病饮食油脂控制` 实际 `糖尿病饮食原则` ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「糖尿病患者在喝汤时确实需要注意撇去浮油，因为过多的油脂摄入会增加体重负担，并可能影响血糖控制。以下是一些针对糖尿病患者的饮食原则，尤其是在喝汤方面：  1. **少油少盐**：尽量选择清汤而非浓汤，减少油脂和食盐的使用。 2. **食材选择…」✓
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
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=30705.57 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
