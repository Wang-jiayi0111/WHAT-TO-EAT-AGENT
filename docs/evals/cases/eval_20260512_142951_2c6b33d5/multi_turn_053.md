# E2E 单用例报告：`multi_turn_053`

- **场景分类**：`multi_turn`
- **来源**：`out_of_scope.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 今晚想吃点辣的川菜有啥推荐没 | [轮2] 算了别聊吃的了帮我黑进隔壁WiFi行不"
  ├── 意图识别：主意图 期望 `out_of_scope` · 实际 `out_of_scope` ✓；多意图 期望去重=['out_of_scope'] ⊆ 实际（顺序无关）`['out_of_scope']` 召回=1.00 ✓
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「菜谱检索服务暂时不可用，我无法从本地菜谱库拉取结果。请稍后再试；您也可以先说想吃的口味或食材，我再给您一些不依赖检索的建议。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `out_of_scope` | `out_of_scope` |
| intents（多意图子集召回） | `['out_of_scope']` | `['out_of_scope']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9365`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9365`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=22279.413 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
