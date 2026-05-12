# E2E 单用例报告：`multi_turn_040`

- **场景分类**：`multi_turn`
- **来源**：`general_chat.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 我儿子最近挑食我都愁死了 | [轮2] 你说我是不是太焦虑了这种事常见吗"
  ├── 意图识别：主意图 期望 `general_chat` · 实际 `general_chat` ✓；多意图 期望去重=['general_chat', 'dietary_advice'] ⊆ 实际（顺序无关）`['general_chat']` 召回=0.50 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「你的心情我完全理解，很多家长都会因为孩子的挑食问题感到焦虑。其实，挑食在儿童中是非常常见的现象，尤其是在2到6岁之间。这个阶段的孩子开始有了自己的喜好和选择，有时候会拒绝尝试新食物或者只吃自己喜欢的食物。  你可以试着放松一些，给自己和孩子…」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `general_chat` | `general_chat` |
| intents（多意图子集召回） | `['general_chat', 'dietary_advice']` | `['general_chat']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.9165`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.9165`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=45261.078 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
