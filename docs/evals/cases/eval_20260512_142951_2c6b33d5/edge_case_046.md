# E2E 单用例报告：`edge_case_046`

- **场景分类**：`edge_case`
- **来源**：`help.json`

## §5.5 业务链路树

```text
用户输入："为啥我每次搜菜谱都说找不到能不能告诉我怎么描述更容易搜到"
  ├── 意图识别：主意图 期望 `help` · 实际 `dietary_advice` ✗；多意图 期望去重=['help'] ⊆ 实际（顺序无关）`['dietary_advice']` 召回=0.00 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「您好！搜索菜谱时，可以尝试以下小技巧，帮助您更快找到心仪的食谱：  1. **使用具体食材名**：比如想要做“鸡肉”，您可以直接输入“鸡胸肉”或“鸡腿肉”等更具体的食材。 2. **加上烹饪方法**：如果知道想用哪种方式来烹饪（如炒、炖、蒸…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `help` | `dietary_advice` |
| intents（多意图子集召回） | `['help']` | `['dietary_advice']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.6815`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.6815`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=19360.531 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
