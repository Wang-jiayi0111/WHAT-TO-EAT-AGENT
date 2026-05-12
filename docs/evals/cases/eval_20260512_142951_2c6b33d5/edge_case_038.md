# E2E 单用例报告：`edge_case_038`

- **场景分类**：`edge_case`
- **来源**：`general_chat.json`

## §5.5 业务链路树

```text
用户输入："你觉得周末先去爬山还是先做家务更解压"
  ├── 意图识别：主意图 期望 `general_chat` · 实际 `general_chat` ✓；多意图 期望去重=['general_chat'] ⊆ 实际（顺序无关）`['general_chat']` 召回=1.00 ✓
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「这得看你个人的喜好啦！如果你喜欢亲近自然，呼吸新鲜空气的话，爬山是个不错的选择，能让你身心都得到放松。而如果你觉得家里整洁了心情会更好，那么先做家务也许会让你感觉更轻松。其实，无论选择哪一种，关键是要让自己开心起来。有时候，换个环境或整理下…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `general_chat` | `general_chat` |
| intents（多意图子集召回） | `['general_chat']` | `['general_chat']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.95`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9500`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=17690.279 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
