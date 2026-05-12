# E2E 单用例报告：`edge_case_041`

- **场景分类**：`edge_case`
- **来源**：`general_chat.json`

## §5.5 业务链路树

```text
用户输入："你这个助手要是连泡面都不会推荐可以下岗了哈哈"
  ├── 意图识别：主意图 期望 `general_chat` · 实际 `general_chat` ✓；多意图 期望去重=['general_chat'] ⊆ 实际（顺序无关）`['general_chat']` 召回=1.00 ✓
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「哈哈，放心吧，关于泡面我还是挺在行的！你喜欢哪种口味的呢？比如经典的红烧牛肉、酸菜牛肉，还是更喜欢海鲜或是蔬菜风味的？或者你有没有什么特别的需求，比如低脂、非油炸之类的？告诉我你的偏好，我来给你推荐几款！」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `general_chat` | `general_chat` |
| intents（多意图子集召回） | `['general_chat']` | `['general_chat']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9865`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9865`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=23706.296 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
