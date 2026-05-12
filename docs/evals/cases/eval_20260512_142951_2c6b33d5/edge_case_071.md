# E2E 单用例报告：`edge_case_071`

- **场景分类**：`edge_case`
- **来源**：`user_clarify.json`

## §5.5 业务链路树

```text
用户输入："既要极辣又要完全不吃辣椒你看着办吧"
  ├── 意图识别：主意图 期望 `user_clarify` · 实际 `profile_sync` ✗；多意图 期望去重=['user_clarify'] ⊆ 实际（顺序无关）`['profile_sync']` 召回=0.00 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。」✗；总分偏低
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `user_clarify` | `profile_sync` |
| intents（多意图子集召回） | `['user_clarify']` | `['profile_sync']` |
| needs_clarification | `True` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.2175`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.2175`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=12130.792 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
