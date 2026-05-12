# E2E 单用例报告：`inventory_045`

- **场景分类**：`inventory`
- **来源**：`help.json`

## §5.5 业务链路树

```text
用户输入："我想入库食材但总说不对格式，有没有示例句式教我一下"
  ├── 意图识别：主意图 期望 `help` · 实际 `inventory_add` ✗；多意图 期望去重=['help'] ⊆ 实际（顺序无关）`['inventory_add', 'help']` 召回=1.00 ✓
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「听起来你可能是在使用某个应用程序或系统来管理你的食材库存，但遇到了一些格式上的问题。通常，这类应用会要求按照特定的格式输入信息，比如“食材名称, 有效期, 数量”这样的格式。不过，不同的应用可能有不同的要求。  如果你能告诉我具体是哪个应用…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `help` | `inventory_add` |
| intents（多意图子集召回） | `['help']` | `['inventory_add', 'help']` |
| needs_clarification | `False` | `True` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.7965`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7965`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=18701.564 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
