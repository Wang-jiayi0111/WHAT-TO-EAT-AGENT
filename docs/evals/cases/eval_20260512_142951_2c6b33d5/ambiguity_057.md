# E2E 单用例报告：`ambiguity_057`

- **场景分类**：`ambiguity`
- **来源**：`recipe_adopt.json`

## §5.5 业务链路树

```text
用户输入："你刚列的清蒸鲈鱼和红烧鲈鱼我定清蒸那条，红烧的不要"
  ├── 意图识别：主意图 期望 `recipe_adopt` · 实际 `recipe_adopt` ✓；多意图 期望去重=['recipe_adopt'] ⊆ 实际（顺序无关）`['recipe_adopt']` 召回=1.00 ✓
  ├── 槽位提取：recipe_adoption≈匹配, recipe_name≈匹配 ✓
  ├── 检索调用：候选标题线索 0 条 ✗
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，已记下您采纳当前这道菜。做完饭后告诉我，我可以按菜谱帮你更新库存。」✗；检索硬失败封顶
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_adopt` | `recipe_adopt` |
| intents（多意图子集召回） | `['recipe_adopt']` | `['recipe_adopt']` |
| needs_clarification | `True` | `False` |
| golden_recipe_ids | `['recipe_id_清蒸鲈鱼']` | `recipe_id_清蒸鲈鱼:未命中` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.330537`（检索硬失败封顶）

- **检索层 §5.1**：aggregate=`0.0000`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.6865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=8721.248 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
