# E2E 单用例报告：`edge_case_024`

- **场景分类**：`edge_case`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："我吃他汀类降脂药，听说不能吃西柚是真的吗具体机制是啥"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `dietary_advice` ✓；多意图 期望去重=['dietary_advice'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=1.00 ✓
  ├── 槽位提取：diet_topic 期望含 `他汀与西柚相互作用` 实际 `他汀类降脂药与西柚的相互作用` ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「确实，服用他汀类降脂药物期间应避免食用西柚。这是因为西柚（包括其果汁）中含有的某些成分能够抑制人体内一种叫做CYP3A4的酶，这种酶负责代谢多种药物，包括大部分的他汀类药物。当CYP3A4被抑制时，会导致他汀类药物在体内的浓度升高，从而增加…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `dietary_advice` | `dietary_advice` |
| intents（多意图子集召回） | `['dietary_advice']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`1.0`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`1.0000`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=25588.189 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
