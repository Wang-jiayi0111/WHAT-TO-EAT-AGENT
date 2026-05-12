# E2E 单用例报告：`inventory_009`

- **场景分类**：`inventory`
- **来源**：`inventory_check.json`

## §5.5 业务链路树

```text
用户输入："冷冻柜里牛肉还剩多少克够不够用"
  ├── 意图识别：主意图 期望 `inventory_check` · 实际 `inventory_check` ✓；多意图 期望去重=['inventory_check'] ⊆ 实际（顺序无关）`['inventory_check']` 召回=1.00 ✓
  ├── 槽位提取：inventory_query_targets≈匹配 ✓
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「您家目前的库存食材如下：    · 五花肉：500.0 g   · 排骨：250.0 g   · 牛筋：500.0 g   · 胡萝卜：1.0 个   · 苦瓜：2.0 根   · 西红柿：1.0 个   · 豆腐：1.0 块   · 饼干…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `inventory_check` | `inventory_check` |
| intents（多意图子集召回） | `['inventory_check']` | `['inventory_check']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.95`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9500`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=5852.578 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
