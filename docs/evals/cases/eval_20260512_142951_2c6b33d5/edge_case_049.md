# E2E 单用例报告：`edge_case_049`

- **场景分类**：`edge_case`
- **来源**：`out_of_scope.json`

## §5.5 业务链路树

```text
用户输入："帮我写一段Python爬虫脚本爬外卖菜单"
  ├── 意图识别：主意图 期望 `out_of_scope` · 实际 `out_of_scope` ✓；多意图 期望去重=['out_of_scope'] ⊆ 实际（顺序无关）`['out_of_scope']` 召回=1.00 ✓
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「我主要帮你做饭谱推荐、库存与买菜清单、饮食偏好这类家事膳食问题。这个问题超出了我的能力范围，换个和吃饭、买菜、菜谱相关的话题我可以陪你聊。」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `out_of_scope` | `out_of_scope` |
| intents（多意图子集召回） | `['out_of_scope']` | `['out_of_scope']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9865`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=4512.179 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
