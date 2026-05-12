# E2E 单用例报告：`multi_turn_023`

- **场景分类**：`multi_turn`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 我对花生严重过敏，帮我记住 | [轮2] 那酱油和调和油里会不会也有花生成分我需要担心吗"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `dietary_advice` ✓；多意图 期望去重=['dietary_advice', 'profile_sync'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=0.50 ✗
  ├── 槽位提取：diet_topic 期望含 `加工调味品过敏原交叉` 实际 `花生成分`, ingredients=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「您提到的确实是个需要注意的问题。有些酱油或调和油可能含有花生成分，或者在生产过程中与花生制品共用设备，导致交叉污染。因此，在购买时，请仔细查看产品的成分表及过敏原信息。如果不确定，最好选择明确标注“不含花生”的产品，或是直接联系生产厂家确认…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `dietary_advice` | `dietary_advice` |
| intents（多意图子集召回） | `['dietary_advice', 'profile_sync']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.905`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9050`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=25436.209 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
