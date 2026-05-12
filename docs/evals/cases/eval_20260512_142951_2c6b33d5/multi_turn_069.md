# E2E 单用例报告：`multi_turn_069`

- **场景分类**：`multi_turn`
- **来源**：`user_clarify.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 鸡肉做法我还没想好口味 | [轮2] 那就限定不加味精且少盐的版本里挑一道吧"
  ├── 意图识别：主意图 期望 `user_clarify` · 实际 `recipe_search` ✗；多意图 期望去重=['user_clarify', 'recipe_search'] ⊆ 实际（顺序无关）`['recipe_search']` 召回=0.50 ✗
  ├── 槽位提取：recipe_query=? ✗
  ├── 检索调用：检索侧候选约 12 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「以下为「姜炒鸡」的用料清单（来自本地菜谱解析）：    · 鸡：650 g   · 食用油：50 ml   · 生姜：250 g   · 啤酒：250 ml   · 生抽：20 ml   · 老抽：10 ml   · 盐：3 g   · 小…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `user_clarify` | `recipe_search` |
| intents（多意图子集召回） | `['user_clarify', 'recipe_search']` | `['recipe_search']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.8575`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`0.9250`
- **对话层 §5.3**：aggregate=`0.7900`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=46933.949 tokens=None mcp≈3

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
