# E2E 单用例报告：`inventory_033`

- **场景分类**：`inventory`
- **来源**：`inventory_commit.json`

## §5.5 业务链路树

```text
用户输入："按刚才那个红烧肉版本扣我的五花肉库存"
  ├── 意图识别：主意图 期望 `inventory_commit` · 实际 `inventory_commit` ✓；多意图 期望去重=['inventory_commit', 'recipe_search'] ⊆ 实际（顺序无关）`['inventory_commit']` 召回=0.50 ✗
  ├── 槽位提取：recipe_name_for_commit≈匹配, deduct_confirm=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「当前没有可用的菜谱用料清单（**R** 为空），库存未变动。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `inventory_commit` | `inventory_commit` |
| intents（多意图子集召回） | `['inventory_commit', 'recipe_search']` | `['inventory_commit']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.8665`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.8665`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=6383.403 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
