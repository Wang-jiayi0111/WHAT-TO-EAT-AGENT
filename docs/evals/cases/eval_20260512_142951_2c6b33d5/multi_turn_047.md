# E2E 单用例报告：`multi_turn_047`

- **场景分类**：`multi_turn`
- **来源**：`help.json`

## §5.5 业务链路树

```text
用户输入："[轮1] 你说的缺口缓存是什么意思我没听懂 | [轮2] 再用一句话比喻解释一下我就不深究了"
  ├── 意图识别：主意图 期望 `help` · 实际 `general_chat` ✗；多意图 期望去重=['help'] ⊆ 实际（顺序无关）`['general_chat']` 召回=0.00 ✗
  ├── 槽位提取：—（fixture 未声明 key_slots）
  ├── 检索调用：检索侧候选约 0 条标题线索（无 golden_recipe_ids 约束） ✓
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「缺口缓存可能是指计算机领域的一个概念，简单来说就像是你家里的储物柜少了一格，用来暂时存放一些东西的空间变小了。不过看起来这和饮食没有直接关系哦，如果是在其他方面遇到了问题，或许可以给我更多的信息，我会尽力帮你解答！」✓
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `help` | `general_chat` |
| intents（多意图子集召回） | `['help']` | `['general_chat']` |
| needs_clarification | `False` | `False` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.7065`

- **检索层 §5.1**：aggregate=`—`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.7065`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=24123.772 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
