# E2E 单用例报告：`edge_case_072`

- **场景分类**：`edge_case`
- **来源**：`user_clarify.json`

## §5.5 业务链路树

```text
用户输入："算了别问我口味了你就当我默认江浙清淡吧继续上一步"
  ├── 意图识别：主意图 期望 `user_clarify` · 实际 `profile_sync` ✗；多意图 期望去重=['user_clarify', 'profile_sync'] ⊆ 实际（顺序无关）`['profile_sync']` 召回=0.50 ✗
  ├── 槽位提取：recipe_query=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `user_clarify` | `profile_sync` |
| intents（多意图子集召回） | `['user_clarify', 'profile_sync']` | `['profile_sync']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.7265`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7265`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=12025.729 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
