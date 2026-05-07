# 开发日志格式规范
# docs/dev_log.md 维护指南

> 维护者：开发 Agent（自动追加）  
> 阅读者：项目负责人、测试 Agent（了解实现决策辅助测试）

---

## 日志文件头（创建时写入一次）

```markdown
# WHAT-TO-EAT-AGENT 开发日志

项目：WHAT-TO-EAT-AGENT  
技术栈：Python · LangGraph  
规格基线：docs/规格设计.md v2.4 · docs/项目说明.md（SRS v1.7）  
日志格式：v1.0  

> 只追加，不修改历史记录。格式规范见 docs/dev_log_format.md。

---
```

---

## 单条记录格式

````markdown
## [DEV-NNN] <简短标题>（15 字以内）

**类型**：`功能开发` | `缺陷修复` | `重构` | `配置`
**编号**：T-xxx（功能）或 BUG-xxx（修复）
**对应规格**：FR-xx / 规格 §x.x
**里程碑**：Mx
**状态**：`已完成` | `部分完成` | `待测试`
**日期**：YYYY-MM-DD

### 做了什么

<!-- 2-4 句话，面向人类，说清楚本次实现/修复了什么 -->

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/state.py` | 新增/修改/删除 | ... |

### 规格对齐要点

<!-- 列出关键实现如何满足规格约束，格式：[规格 §x.x / FR-xx] 说明 -->
- [规格 §1.2.0] ...
- [FR-xx] ...

### 规格偏差（若有）

<!-- 若有临时偏差必须说明原因和解决计划；完全对齐则写"无" -->
无

### 修复详情（仅 type=缺陷修复 时填）

缺陷：BUG-xxx  
根因：<一句话>  
修复：<说明修改了什么>

### 遗留问题

<!-- 本次有意跳过、已知限制，说明在哪个任务处理 -->
- [ ] <问题>（T-xxx 处理）

### 关联

前置：T-xxx ✓  
后续：T-xxx（依赖本次）  
测试覆盖：S-0x / `tests/test_xxx.py::test_xxx`

---
````

---

## 字段说明

**DEV-NNN**：全局自增流水号，功能开发与缺陷修复共用序列，从 DEV-001 起**连续编号**，与开发计划 `T-xxx` **无一一对应**（例如任务 T-009 记录在 [DEV-011]）。新增条目取 **当前最大 DEV 编号 + 1**（截至仓库现状，最后一条为 [DEV-017]，下一条应为 **DEV-018**）。`docs/dev_log.md` 正文里各节应按 **DEV 数值递增**排版；若误用了大号（历史曾出现跳至 DEV-030），应统一改正文标题与全库交叉引用，而非保留空洞号段。

**类型**：

| 类型 | 说明 |
|------|------|
| `功能开发` | 对应 T-xxx |
| `缺陷修复` | 对应 BUG-xxx |
| `重构` | 不改外部行为的内部调整 |
| `配置` | 仅涉及配置/文档 |

**状态**：

| 状态 | 含义 |
|------|------|
| `已完成` | 开发自验通过，等待测试 Agent |
| `部分完成` | 仅实现任务的一部分 |
| `待测试` | 修复已提交，等待测试 Agent 复审 |

---

## 注意事项

1. **只追加，不修改正文**：已有条目的标题与正文不因后续迭代改写；需补充时追加新条目，标题注明「（补充 DEV-xxx）」。**例外**：若误粘贴导致章节顺序与 DEV 编号不一致，允许**仅调整节的先后顺序**（不改标题与内容），以保持检索一致性。
2. **代码不进日志**：只记录决策摘要，完整代码在源文件
3. **BUG 编号由测试 Agent 分配**：开发 Agent 直接引用，不自行分配
4. **完成日志后同步开发计划**：更新 `docs/开发计划.md` 对应任务的状态列

---

## 示例 A：功能开发

```markdown
## [DEV-009] AgentState 七切片落地（编号示例：流水号与 T-xxx 独立）

**类型**：`功能开发`
**编号**：T-030
**对应规格**：规格 §1.2.0～1.2.1；SRS §7.2
**里程碑**：M1
**状态**：`已完成`
**日期**：2026-05-06

### 做了什么

在 state.py 中引入方案 A 的七个顶层切片 TypedDict，将 inventory_snapshot 从 List[Dict] 迁移为 Dict[str, {amount, unit}]，建立兼容层与 logistics_buffer 双向同步。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/state.py` | 修改 | 新增七切片 TypedDict；active_user_id 保留顶层 |
| `src/agent/compat.py` | 新增 | 兼容层：旧 buffer 与新切片双向读写 |

### 规格对齐要点

- [规格 §1.2.0] 七切片为 AgentState 一级键，messages 使用 add_messages 归约，其余整对象替换
- [规格 §1.2.1] inventory_snapshot 定型为 Dict[str, {amount, unit}]，注释标注「禁止 List[Dict]（规格 §1.2.1）」
- [SRS §7.2.2] 当前处于三阶段迁移的阶段1，新代码通过访问器读写

### 规格偏差（若有）

兼容层暂时双写 logistics_buffer，预计 T-031 完成后进入阶段2。

### 遗留问题

- [ ] 旧 checkpoint 缺键处理（空切片默认值）（M6 T-029 前完成）
- [ ] active_constraints → memory_state.short_term_constraints 合并（T-010 处理）

### 关联

前置：T-001 ✓  
后续：T-002、T-031（依赖本次七切片结构）  
测试覆盖：`tests/test_state.py::test_seven_slice_structure`

---
```

## 示例 B：缺陷修复

```markdown
## [DEV-007] 修复摘要节点误清 recipe_state

**类型**：`缺陷修复`
**编号**：BUG-003
**对应规格**：FR-14, FR-16；规格 §4.2
**里程碑**：M2
**状态**：`待测试`
**日期**：2026-05-10

### 做了什么

修复 L2 摘要节点在多轮对话后意外清空 recipe_state.recipe_requirements 的问题，导致 S-08 场景下用户索要购物清单时无法从缓存交付。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/nodes/memory.py` | 修改 | 摘要节点仅返回 memory_state 切片，不再返回完整 state |

### 规格对齐要点

- [规格 §4.2] 摘要节点现在只更新 memory_state 和 dialog_state.messages，注释「禁止修改 recipe_state/inventory_state/task_stack（规格 §4.2）」

### 规格偏差（若有）

无

### 修复详情

缺陷：BUG-003  
根因：summarize_node 返回完整 state dict，LangGraph 整对象替换时用空值覆盖了 recipe_state  
修复：将返回值从 {**state, "memory_state": ...} 改为仅返回 {"memory_state": ..., "dialog_state": ...}

### 遗留问题

无

### 关联

前置：T-009 ✓  
后续：无  
测试覆盖：S-08；`tests/test_memory.py::test_summary_preserves_recipe_state`

---
```
