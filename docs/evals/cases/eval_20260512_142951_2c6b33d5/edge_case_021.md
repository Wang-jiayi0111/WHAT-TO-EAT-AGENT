# E2E 单用例报告：`edge_case_021`

- **场景分类**：`edge_case`
- **来源**：`dietary_advice.json`

## §5.5 业务链路树

```text
用户输入："我有胃溃疡但又特别想吃重庆火锅级别的辣，你给个权威说法行不行"
  ├── 意图识别：主意图 期望 `dietary_advice` · 实际 `profile_sync` ✗；多意图 期望去重=['dietary_advice'] ⊆ 实际（顺序无关）`['profile_sync', 'dietary_advice']` 召回=1.00 ✓
  ├── 槽位提取：diet_topic 期望含 `胃病与辛辣饮食冲突` 实际 `胃溃疡与辛辣食物` ✗
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。  哎呀，理解你对重庆火锅的热爱，但考虑到你的胃溃疡情况，真的得小心点哦。辛辣食物可能会刺激胃黏膜，加重溃疡症状，甚至引起疼痛。建议先以温和饮食为主，等身体恢复得差不多了，再偶尔尝试一点点辣…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `dietary_advice` | `profile_sync` |
| intents（多意图子集召回） | `['dietary_advice']` | `['profile_sync', 'dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.86`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.8600`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=23899.659 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
