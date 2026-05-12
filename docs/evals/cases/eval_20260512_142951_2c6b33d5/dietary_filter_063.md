# E2E 单用例报告：`dietary_filter_063`

- **场景分类**：`dietary_filter`
- **来源**：`profile_sync.json`

## §5.5 业务链路树

```text
用户输入："我是严格素食者请以后推荐菜谱都不要出现肉类高汤等隐形荤料"
  ├── 意图识别：主意图 期望 `profile_sync` · 实际 `profile_sync` ✓；多意图 期望去重=['profile_sync'] ⊆ 实际（顺序无关）`['profile_sync']` 召回=1.00 ✓
  ├── 槽位提取：profile_fragments 期望含 `['纯素食', '避免肉类高汤']` 实际 `['不吃肉', '不使用高汤']`, profile_explicit=? ✗
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
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=10550.235 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
