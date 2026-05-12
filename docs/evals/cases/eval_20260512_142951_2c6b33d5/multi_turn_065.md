# E2E 单用例报告：`multi_turn_065`

- **场景分类**：`multi_turn`
- **来源**：`profile_sync.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 其实我海鲜并不过敏之前说错了 | [轮2] 真正需要注意的是我对芒果过敏请覆盖之前的记录"
  ├── 意图识别：主意图 期望 `profile_sync` · 实际 `profile_sync` ✓；多意图 期望去重=['profile_sync'] ⊆ 实际（顺序无关）`['profile_sync']` 召回=1.00 ✓
  ├── 槽位提取：profile_fragments 期望含 `['纠正海鲜过敏误判', '芒果过敏']` 实际 `['对芒果过敏']`, profile_explicit=? ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `profile_sync` | `profile_sync` |
| intents（多意图子集召回） | `['profile_sync']` | `['profile_sync']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9365`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9365`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=13051.021 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
