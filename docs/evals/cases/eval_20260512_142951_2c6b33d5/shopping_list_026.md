# E2E 单用例报告：`shopping_list_026`

- **场景分类**：`shopping_list`
- **来源**：`shopping_list.json`

## §5.5 业务链路树

```text
用户输入："周末请客这顿饭我还缺啥要我下班顺便买回来"
  ├── 意图识别：主意图 期望 `shopping_list` · 实际 `shopping_list` ✓；多意图 期望去重=['shopping_list'] ⊆ 实际（顺序无关）`['shopping_list']` 召回=1.00 ✓
  ├── 槽位提取：list_action=? ✗
  ├── 检索调用：检索侧候选约 1 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「抱歉，我没有找到合适的菜谱，请换个关键词再试试？」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `shopping_list` | `shopping_list` |
| intents（多意图子集召回） | `['shopping_list']` | `['shopping_list']` |
| needs_clarification | `False` | `True` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.825833`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.6865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=6561.879 tokens=None mcp≈2

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
