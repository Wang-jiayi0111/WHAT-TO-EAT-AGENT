# WHAT-TO-EAT-AGENT 开发日志

项目：WHAT-TO-EAT-AGENT  
技术栈：Python · LangGraph  
规格基线：docs/规格设计.md v2.4 · docs/项目说明.md（SRS v1.7）  
日志格式：v1.0  

> 只追加，不修改历史记录。格式规范见 docs/dev_log_format.md。

---

<!-- 开发 Agent 从此处开始追加记录 -->

## [DEV-001] M0 基线路由快照与 pytest 夹具

**类型**：`功能开发`  
**编号**：T-001  
**对应规格**：NFR-05；规格 §10（编排路径 `workflow.py`）；里程碑 M0  
**里程碑**：M0  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

建立 `tests/conftest.py` 中最小 `logistics_buffer` / `AgentState` 片段工厂与 fixture；新增 `test_workflow_routing_baseline.py`，对 `workflow.py` 四条条件路由函数做表驱动调用并与黄金 JSON 比对；配置 `pytest.ini` / `pyproject.toml` 的 `python_files = test_*.py`，避免脚本型 `*_test.py` 被收集。  

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `tests/conftest.py` | 新增 | 路径与状态工厂、fixture |
| `tests/unit/test_workflow_routing_baseline.py` | 新增 | 路由快照测试 |
| `tests/snapshots/workflow_routing_baseline.json` | 新增 | 黄金快照 |
| `pytest.ini` | 修改 | `python_files` |
| `pyproject.toml` | 修改 | `python_files`（与上互补） |
| `docs/T-001_基线测试说明.md` | 新增 | T-001 开发说明（维护约定与范围） |
| `docs/开发计划.md` | 修改 | T-001 状态与备注 |

### 规格对齐要点

- [NFR-05] 核心路径具备可自动化执行的单测（当前锚定编排条件边，无外部 I/O）。
- [规格 §10] 与「编排」目录映射一致，快照锁定 `workflow.py` 路由行为。
- [M0] 刻意对齐**现状**扁平状态；七切片夹具留待 T-030（规格 §1.2.0 / `dev_agent_prompt` 方案 A）。

### 规格偏差（若有）

无（M0 允许仅覆盖现状路由；方案 A 非本任务范围）。

### 遗留问题

- [ ] `make_minimal_agent_state` 在 T-030 后改为基于 `control_state` / `recipe_state` 或提供访问器（T-030）。
- [ ] `task_stack`「执行即出队」单测在 T-003 补强。

### 关联

前置：无  
后续：T-002、T-032（开发计划标注依赖 T-001）  
测试覆盖：`tests/unit/test_workflow_routing_baseline.py`（结论以测试 Agent `docs/test_report.md` 为准）

---

## [DEV-002] logistics 静默缺口预计算（§1.3 步 5 / §7.1）

**类型**：`功能开发`  
**编号**：T-002  
**对应规格**：规格 §1.3 步 5；§7.1～§7.2；SRS §6.1（按需分流）；NFR-05（可测）  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

在 `logistics_manager_node` 末尾增加 `_apply_silent_gap_precalc`：当合并后的 `recipe_requirements`（**R**）非空时，在 **TASK_INV_COMMIT / TASK_INV_ADD** 等可能修改库存的分支之后，再次 `get_inventory_snapshot()` 拉取最新 **I**，用既有 `calculate_shopping_gap` 写入 `cached_shopping_gap`（含 `computed_at`、`pending_manual`）、`gap_basis`（`recipe_title`、`r_fingerprint`、`inventory_fingerprint`），并保留顶层 `shopping_list` 等兼容字段。`TASK_GAP_CALC` 分支去掉重复的缺口计算，避免与静默路径双算。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/nodes/logistics.py` | 修改 | 指纹辅助函数 + 静默预计算；模块文档 |
| `src/agent/workflow.py` | 修改 | 顶部注释对齐 researcher→logistics 行为 |
| `tests/unit/test_logistics_silent_gap.py` | 新增 | 指纹稳定性 + mock 下的缓存断言 |
| `docs/开发计划.md` | 修改 | T-002 开发/测试状态 |

### 规格对齐要点

- [规格 §1.3 步 5] **R** 非空且拉取 **I** 后 logistics **必须**执行 §7.2 并写缓存；不要求用户本轮清单意图。
- [规格 §7.1～7.2] `cached_shopping_gap` 结构含 `shopping_list` / `sufficient_items` / `missing_items` / `pending_manual` / `computed_at`；`gap_basis` 含指纹与菜名。
- [规格 §7.5] R/I 逐项规范化后续任务补充；本实现沿用现有 `calculate_shopping_gap` 键名匹配。

### 规格偏差（若有）

`inventory_state` 七切片与字段迁入 **T-030** 前，缓存仍写入 `logistics_buffer`（与现有 generator 读路径一致）。

### 遗留问题

- [ ] 用户仅 `TASK_INV_CHECK` 且无 **R** 时不触发静默预计算（符合 §7.1「R 非空」）。
- [ ] `normalize_name` 接入 gap 计算（§7.5）建议在 T-023/T-024 统一。

### 关联

前置：T-001 ✓  
后续：T-030（切片字段迁移）、T-023（清单缓存读路径）  
测试覆盖：`tests/unit/test_logistics_silent_gap.py`（结论以测试 Agent 为准）

---

## [DEV-003] task_stack 执行即出队与 generator 调度顺序

**类型**：`功能开发`  
**编号**：T-003  
**对应规格**：FR-04；规格 §11.4  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 `src/agent/task_stack.py`：`consume_tasks`、`first_present`、`GENERATOR_REPLY_TASK_ORDER` / `ROUTER_TASK_PRIORITY` 文档常量。`generator` 对成果类任务按固定顺序取首个命中任务并出队；澄清分支区分「有候选等待用户」与「无候选」的消费集合；删除 `handle_clarify` 内对 `state.task_stack` 的原地修改。`researcher`、`clarify_resolver` 对 `TASK_SEARCH`/`TASK_CLARIFY` 的移除改为 `consume_tasks`。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/task_stack.py` | 新增 | 出队工具与优先级元组 |
| `src/agent/nodes/generator.py` | 修改 | 统一消费语义与多任务调度 |
| `src/agent/nodes/researcher.py` | 修改 | consume_tasks |
| `src/agent/nodes/clarify_resolver.py` | 修改 | consume_tasks |
| `src/agent/state.py` | 修改 | task_stack 注释指向 FR-04 |
| `tests/unit/test_task_stack.py` | 新增 | 工具函数行为 |

### 规格对齐要点

- [FR-04 / §11.4] 任务执行后轮转出队；禁止依赖「集合包含」而不移除已执行标记。
- [dev_agent_prompt] 仅用 `task_stack` 命名。

### 规格偏差（若有）

无。

### 遗留问题

- [ ] FR-50 全量多意图仲裁优先级（T-007）可细化 `ROUTER_TASK_PRIORITY` 与路由 jointly。

### 关联

前置：T-002 ✓  
后续：T-004（路由结构化输出）、T-007  
测试覆盖：`tests/unit/test_task_stack.py`

---

## [DEV-004] router 结构化输出（FR-01 / §11.1）

**类型**：`功能开发`  
**编号**：T-004  
**对应规格**：FR-01；规格 §11.1（primary、intents、confidence、needs_clarification、slots）  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

`get_intent_details` 与 `router_node` 统一写出 `primary_intent`、`intents`、`secondary_intents`、`confidence`、`needs_clarification`；`slots` 与 `entities` 同构；`missing_slots` 暂空列表（T-031）。综合置信度低于 0.6 时 `needs_clarification=True` 并走 `TASK_CLARIFY`（阈值后续 T-005 接入配置）。`INTENT_TASK_MAPPING` 增加 `dietary_advice`。修正 `IntentResult` 重复 `reasoning` 字段定义。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/state.py` | 修改 | NotRequired：意图与 slots 字段 |
| `src/agent/nodes/router.py` | 修改 | 结构化输出与常量阈值 |
| `src/agent/nodes/schema.py` | 修改 | 去除重复 Field |
| `tests/unit/test_router_structured_output.py` | 新增 | mock 分类器契约 |

### 规格对齐要点

- [FR-01] 每轮可观测：意图列表、实体槽位、综合置信度、是否澄清。
- [§11.1] `primary_intent` 与 `intents[0]` 一致；`slots` 承载迁移期实体命名空间。

### 遗留问题

- [ ] `intent.confidence.clarify_threshold` 来自配置（T-005）。
- [ ] `missing_slots` 必填槽推导（T-031）。

### 关联

前置：T-003 ✓  
后续：T-005、T-031  
测试覆盖：`tests/unit/test_router_structured_output.py`

---

## [DEV-005] 意图置信度阈值配置与澄清分支（T-005）

**类型**：`功能开发`  
**编号**：T-005  
**对应规格**：FR-03；规格 §8、`intent.confidence.clarify_threshold`；§11.6  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

`Settings.get_intent_clarify_threshold()` 读取 `config/setting.yaml` 中 `intent.confidence.clarify_threshold`（缺省 **0.55**，与规格 §8 表一致）。`IntentClassifier` 在初始化时保存 `self.clarify_threshold`，`get_intent_details` 用其与模型综合置信度比较：低于阈值则 `needs_clarification=True`、仅 `TASK_CLARIFY`、不映射写库类任务（FR-03）。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/libs/base/settings.py` | 修改 | `get_intent_clarify_threshold` |
| `config/setting.yaml` | 修改 | `intent.confidence` 段 |
| `src/agent/nodes/router.py` | 修改 | 实例阈值替代模块常量 |
| `tests/unit/test_settings_intent_threshold.py` | 新增 | 配置解析单测 |

### 规格对齐要点

- [§8] 配置键与默认值 0.55；可调参。
- [FR-03 / §11.6] 低置信不展开 `TASK_INV_*` / 画像写路径。

### 遗留问题

无。

### 关联

前置：T-004 ✓  
后续：T-006（元意图话术可共用阈值语义）  
测试覆盖：`tests/unit/test_settings_intent_threshold.py`

---

## [DEV-006] 元意图与 dietary_advice / recipe_adopt（T-006）

**类型**：`功能开发`  
**编号**：T-006  
**对应规格**：FR-02；规格 §11.3～§11.4  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

`IntentResult.intents` 扩展 `help`、`out_of_scope`、`recipe_adopt`；`INTENT_TASK_MAPPING` 补全上述及既有 `dietary_advice` → `TASK_DIRECT_REPLY`。`intent_prompt.md` 增加对应类别说明与 `diet_topic` 实体键；修正 Response Format 中全角逗号。`GeneratorNode.handle_direct_reply` 按 `primary_intent` 分支：`help`/`out_of_scope` 固定话术，`dietary_advice` 专用系统提示 + LLM，`recipe_adopt` 占位回复（与 `recipe_use_confirmed` 衔接留 T-021）；默认仍走闲聊。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/nodes/schema.py` | 修改 | Literal 扩展 |
| `src/agent/nodes/router.py` | 修改 | 映射表 |
| `src/agent/nodes/generator.py` | 修改 | 元意图分支与常量文案 |
| `src/agent/prompts/intent_prompt.md` | 修改 | 意图与实体说明 |
| `tests/unit/test_meta_intent_replies.py` | 新增 | 分支单测 |

### 规格对齐要点

- [FR-02] 支持帮助、超范围、闲聊路径区分。
- [§11.4] help / out_of_scope / general_chat / dietary_advice 均落 `TASK_DIRECT_REPLY`，由 generator 提示词区分。

### 遗留问题

- [ ] `recipe_adopt` 写 `inventory_state.recipe_use_confirmed`（T-030 + T-021）。

### 关联

前置：T-004 ✓  
后续：T-007（多意图优先级）、T-031（槽位）  
测试覆盖：`tests/unit/test_meta_intent_replies.py`

---

## [DEV-007] 多意图 FR-50 仲裁与 task_stack 顺序（T-007）

**类型**：`功能开发`  
**编号**：T-007  
**对应规格**：FR-50、FR-51；规格 §11.4（`intents` 有序）  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 `src/agent/intent_priority.py`：`FR50_INTENT_RANK` 与 `sort_intents_by_fr50`。`get_intent_details` 在置信度检查前对模型返回的 `intents` 做 FR-50 重排，重算 `primary_intent` / `secondary_intents`，并按重排后的意图顺序展开 `task_stack`（去重时保留先出现的任务，与意图顺序一致）。`workflow.py` 头部注明单线程图满足 FR-51。`intent_prompt.md` 规则 2 改为说明路由层重排。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/intent_priority.py` | 新增 | FR-50 排序 |
| `src/agent/nodes/router.py` | 修改 | 接入排序与日志 |
| `src/agent/workflow.py` | 修改 | FR-51 说明 |
| `src/agent/prompts/intent_prompt.md` | 修改 | 多意图规则 |
| `tests/unit/test_intent_priority_fr50.py` | 新增 | 排序单测 |

### 规格对齐要点

- [FR-50] 画像 > 定菜/清单 > 库存侧 > 闲聊类元意图。
- [FR-51] 共享状态仅由 LangGraph 顺序执行节点写入；`task_stack` 顺序与仲裁后意图一致。

### 遗留问题

- [ ] 更细的「硬禁忌优先」可与 `profile_sync` + 置信策略在 T-011/T-031 强化。

### 关联

前置：T-004 ✓  
后续：T-008（次意图合并答复）、T-031  
测试覆盖：`tests/unit/test_intent_priority_fr50.py`

---

## [DEV-008] 次意图合并答复（FR-52）（T-008）

**类型**：`功能开发`  
**编号**：T-008  
**对应规格**：FR-52  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

在 `generator_node` 成果收集阶段，不再仅用「优先级表首个命中」单段回复；改为按 **`task_stack` 从左到右**扫描 `MERGEABLE_GENERATOR_TASKS`，依次调用既有 `handle_*`，将非空段落用 `\n\n` 合并为 **一条** `AIMessage`，并从栈中移除本轮已处理的合并类标记（`TASK_SEARCH` 等非合并项保留在原相对顺序）。`TASK_SUMMARIZE` 之后的 **`pending_tasks` 回填**逻辑保留（可多批 summarize 顺序追加）。若成果段均为空，则不消费栈并打日志。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/nodes/generator.py` | 修改 | `_collect_merged_generator_reply`、`MERGEABLE_GENERATOR_TASKS` |
| `tests/unit/test_generator_merged_replies.py` | 新增 | 合并顺序、保留 SEARCH、pending、降级 DIRECT_REPLY |

### 规格对齐要点

- [FR-52] 次意图在主意图相关节点完成后，用户可见侧 **顺序对应 stack**，并以 **单条合并答复** 交付（与 FR-50 排序后的 stack 一致）。

### 遗留问题

- [ ] 若需「分段多条气泡」UI，需在编排层拆 AIMessage（当前仍为单条 content）。

### 关联

前置：T-007 ✓  
后续：T-031  
测试覆盖：`tests/unit/test_generator_merged_replies.py`

---

## [DEV-009] 方案 A 七切片、访问器与移除 logistics_buffer（T-030）

**类型**：`功能开发`  
**编号**：T-030  
**对应规格**：规格 §1.2.0～1.2.1；SRS §7.2（状态语义）  
**里程碑**：M1  
**状态**：`已完成`（阶段 1～3 本轮收敛：切片 + `get_runtime_bundle` + 删除顶层 buffer 键）  
**日期**：2026-05-06  

### 做了什么

**阶段 1（早前）**：`AgentState` 七切片、`merge_slice`、`empty_agent_slices`、`state_sync` 从展平 bundle 推导各切片。

**阶段 2**：新增 **`state_accessors.get_runtime_bundle(state)`**——优先从切片 **`materialize_runtime_bundle_from_slices`** 组装展平视图；若 checkpoint **仅有旧 `logistics_buffer`** 且切片尚无业务载荷，则沿用 buffer。节点侧统一通过 **`get_runtime_bundle`** / **`runtime_bundle_to_slice_patches`** 读写，取代散落 `state["logistics_buffer"]`。

**阶段 3**：从 **`AgentState` TypedDict 删除 `logistics_buffer`**；路由将 **`extracted_entities` / `router_reasoning`** 写入 **`control_state`**；各节点 **`return`** 仅输出 **切片补丁**（不再写 buffer 键）。**`control_state_from_logistics_buffer`**、**`empty_runtime_bundle`**、展平键向 **`inventory_state`** 的透传（shopping_list 等）支撑 round-trip。

**其它**：**`_recipe_candidates_to_legacy_shape`** 对无 `title`/`name` 的 dict 候选保留原 dict，避免路由单测与 MCP 原始条目被清空。

### 变更文件（阶段 2～3 追加）

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/state_accessors.py` | 新增 | `get_runtime_bundle` |
| `src/agent/state_sync.py` | 修改 | 展平组装、`runtime_bundle_to_slice_patches`、`empty_runtime_bundle`、`control_state_*` |
| `src/agent/state.py` | 修改 | 移除 `LogisticsBuffer` / `logistics_buffer` 键 |
| `workflow.py`、`slot_filling.py`、`nodes/*` | 修改 | 访问器与切片 `return` |
| `tests/conftest.py`、`test_*` | 修改 | 夹具与断言对齐切片 |

### 规格对齐要点

- [§1.2.0] 业务状态以切片为唯一持久形状；展平 bundle 为运行时视图。  
- [§1.2.1] `inventory_snapshot` 字典型 **I** 仍在 `inventory_state`。  

### 遗留问题

- [ ] **`messages` → `dialog_state.messages`** 与 LangGraph `add_messages` 归约迁移（独立变更）。  
- [ ] 旧持久化线程若含 **`logistics_buffer`**，`get_runtime_bundle` 仍会读取该键直至用户清空 checkpoint。

### 关联

前置：T-002 ✓  
后续：T-020 / T-023 / T-009  
测试覆盖：`pytest tests/unit`（25 passed）

---

## [DEV-010] 槽位归一、必填校验与任务栈守卫（T-031）

**类型**：`功能开发`  
**编号**：T-031  
**对应规格**：规格 §11.2～11.5；`IntentResult` / `intent_prompt`  
**里程碑**：M1  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 `src/agent/slot_filling.py`：`normalize_legacy_entities_to_slots` 将历史 `entities`（含 `amounts`、`preferences`、`check_inventory` 等）收敛到 §11.2 槽位键；`compute_missing_slots` 实现 §11.5 最小必填（含同轮 `recipe_search`+`shopping_list` 时对 **R** 未就绪的豁免）；`apply_slot_guards_to_task_stack` 按缺失码裁剪对应意图产生的任务，并在有缺失时在队首插入 `TASK_CLARIFY`。`IntentResult` 增加 `slots`、`missing_slots` 字段，`intents` Literal 补 `user_clarify`。路由在高置信路径合并模型与规则侧的 `missing_slots`，并将 `needs_clarification` 与必填缺口对齐。`intent_prompt.md` 补充 §11.2 键说明与响应格式中的 `slots` / `missing_slots`。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/slot_filling.py` | 新增 | 归一、缺失计算、task_stack 守卫 |
| `src/agent/nodes/schema.py` | 修改 | `IntentResult.slots` / `missing_slots`、`user_clarify` |
| `src/agent/nodes/router.py` | 修改 | 接入槽位管线 |
| `src/agent/prompts/intent_prompt.md` | 修改 | §11.2 与 JSON 契约 |

### 规格对齐要点

- [§11.2] 全局槽位命名空间与兼容别名归一。  
- [§11.5] 必填缺口 → `missing_slots`，并禁止对缺口意图展开写库类任务（裁剪 + 澄清）。  

### 遗留问题

- [ ] 槽位澄清与「选菜澄清」在生成器侧话术分流仍可按 §11.6 细化。  
- [ ] `inventory_query_targets` 由模型直接产出可减少对 `check_inventory` 的依赖。

### 关联

前置：T-004 ✓  
后续：T-009 / T-011 / T-029  
测试覆盖：本轮按迭代约定未新增自动化用例。

---

## [DEV-011] L2 摘要节点与业务状态解耦（T-009）

**类型**：`功能开发`  
**编号**：T-009  
**对应规格**：FR-14，FR-16；**规格 §4.2**（L2 仅更新 messages 与 conversation_summary；禁止改 task_stack / recipe / inventory 澄清相关字段）  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

从 `conversation_summary_node` 删除「按 task_stack 是否为空」分支中对 `task_stack`、`expert_payloads` 及 `runtime_bundle_to_slice_patches(empty_runtime_bundle())` 的清场/重置逻辑；删除调试 `print`。L2 仅在存在 `messages` 时返回 `messages` 裁剪结果、`conversation_summary` 与 `memory_state["conversation_summary"]` 镜像补丁，不再调用 `memory_state_patch_from_summary_and_constraints`（避免在 L2 掺写 `short_term_constraints`）。`existing_summary` 优先读取 `memory_state.conversation_summary`。`state_sync.memory_state_patch_from_summary_and_constraints` 增加文档说明：仅供非 L2 路径使用。`workflow.py` 顶部编排注释对齐 §4.2。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/nodes/conversation_summary.py` | 修改 | L2 纯化；模块文档 |
| `src/agent/state_sync.py` | 修改 | 合并函数文档约束 |
| `src/agent/workflow.py` | 修改 | 节点职责注释 |
| `docs/开发计划.md` | 修改 | T-009 开发/测试状态 |

### 规格对齐要点

- [§4.2] L2 **仅** messages 裁剪 + `conversation_summary`（及镜像 `memory_state` 摘要键）。  
- [FR-14/16] 摘要与业务「清场」解耦：澄清等待态不再依赖 L2 分支「保护现场」。  

### 规格偏差（若有）

无。

### 遗留问题

- [x] §4.3 L3 独立节点与 `memory_state.short_term_constraints` 写入路径：**T-010 / DEV-012** 已落地。  
- [ ] `messages` 与 `add_messages` 归约下「裁剪」语义见 `docs/dev_log.md` [DEV-009] 遗留项。  

### 关联

前置：T-002 ✓  
后续：T-011（C 合并）、T-013（TTL）  
测试覆盖：本轮按约定未新增单测；回归以测试 Agent 为准。  

---

## [DEV-012] L3 当轮约束节点与检索 query 增强（T-010）

**类型**：`功能开发`  
**编号**：T-010  
**对应规格**：FR-17；**规格 §4.3**（`memory_state.short_term_constraints`）、§4.6 编排（L2→L3→router 前序）；检索侧为 **C** 的增量注入（完整 EffectiveConstraint 见 T-011）  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 **`src/agent/l3_short_term.py`**：可配置关键词规则（`Settings` → `memory.l3.keyword_rules`，缺省用内置表）、`latest_user_text`、`extract_short_term_lines`、`merge_short_term_constraints`、`augment_query_for_search`（合并 `get_runtime_bundle` 中 L3 行与顶层 `active_constraints` 追加至 MCP `search_recipes` 的 query）。新增 **`src/agent/nodes/short_term.py`**：`short_term_constraints_node` 仅写 **`memory_state`**（及命中时 **`memory_confidence`**）。**`workflow.py`**：`conversation_summary` → **`short_term`** → `memory_keeper` → `router`。**`researcher.py`**：阶段一检索前对 `query` 调用 **`augment_query_for_search`**。**`config/setting.yaml`**：增加 **`memory.l3.keyword_rules`** 示例表。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/l3_short_term.py` | 新增 | L3 抽取与 query 增强 |
| `src/agent/nodes/short_term.py` | 新增 | LangGraph L3 节点 |
| `src/agent/workflow.py` | 修改 | 注册节点与边 |
| `src/agent/nodes/researcher.py` | 修改 | 检索 query 增强 |
| `config/setting.yaml` | 修改 | `memory.l3` |
| `docs/开发计划.md` | 修改 | T-010 状态 |

### 规格对齐要点

- [§4.3] 输入最新用户句；输出 `memory_state.short_term_constraints`；规则表可配置。  
- [§4.6] L3 位于 L2 之后、router 之前。  
- [FR-17] 当轮约束进入检索前 query（与 **C** 对齐的下一步为 T-011）。  

### 规格偏差（若有）

`memory_keeper` 仍同步执行于 router 之前（与 §4.6 图中「L4 在 generator 后异步」不完全一致；异步化属 **T-012**）。

### 遗留问题

- [x] §3.5 合并 **C** 与检索链路：**T-011 / DEV-013** 已在 `researcher` 与 `effective_constraint.py` 落地。  
- [ ] L3 命中与 `memory_confidence` 标量策略可随线上数据调参。  

### 关联

前置：T-009 ✓  
后续：T-015（检索统一 **C** 全链路复核）、T-012（L4 异步）  
测试覆盖：`pytest tests/unit`（29 passed，本轮未新增 L3 专用用例）

---

## [DEV-013] 有效约束 **C** 合并与 §5.4 硬过滤（T-011）

**类型**：`功能开发`  
**编号**：T-011  
**对应规格**：FR-10，FR-11，FR-19；**规格 §3.5、§5.4**  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 **`src/agent/effective_constraint.py`**：`resolve_scope_id`、`build_effective_constraint`（长期画像 + DB `short_term_states` + `memory_state.short_term_constraints` + L2 摘要截断）、`augment_search_query`（检索语义增强）、`filter_recipes_by_hard_exclusions`（§5.4 菜名/摘要字段命中 **hard_exclusions** 即剔除）。**`researcher.py`**：每轮构建 **C**，`search_recipes` 使用 **`scope_id`**（与 **`household.default_id`** 对齐），阶段一结果先 **硬过滤** 再进入置信/歧义分支；**`memory_state.effective_constraint`** 回写。 **`state_sync.materialize_runtime_bundle_from_slices`** 展平 `effective_constraint`。**`config/setting.yaml`** 增加 **`household.default_id`**；**`Settings.get_scope_id`** 供复用。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/effective_constraint.py` | 新增 | **C** 与过滤 |
| `src/agent/nodes/researcher.py` | 修改 | 合并、query、§5.4、MCP scope |
| `src/agent/state_sync.py` | 修改 | 展平 `effective_constraint` |
| `config/setting.yaml` | 修改 | `household` |
| `src/libs/base/settings.py` | 修改 | `get_scope_id` |
| `docs/开发计划.md` | 修改 | T-011 状态 |

### 规格对齐要点

- [§3.5] **hard_exclusions** / **temporal_conditions** / **summary_snippet** 等字段与合并步骤一致。  
- [§5.4] 检索返回候选按禁忌关键词二次过滤；剔尽可走原有「无结果」降级。  
- [§5.1] **user_id** 传 **SCOPE_ID**（`household.default_id`）。  

### 规格偏差（若有）

画像缺失或 DB 不可用时 **C** 退化为仅 L2+L3+`active_constraints`（`build_effective_constraint` 捕获异常后空画像）。

### 遗留问题

- [ ] 禁忌词匹配粒度（ substring）误杀/漏杀可按线上日志调 **§7.5** `normalize_name` 同类策略。  
- [x] **L4** 异步化后 **C** 不含当轮异步写库结果（仅下一用户轮 `build_effective_constraint` 读库可见）；见 **T-012 / DEV-014**。  

### 关联

前置：T-010 ✓  
后续：T-012、T-015  
测试覆盖：`pytest tests/unit`（37 passed，未新增 T-011 专测）

---

## [DEV-014] L4 MemoryKeeper 异步与编排对齐 §4.5～4.6（T-012）

**类型**：`功能开发`  
**编号**：T-012  
**对应规格**：FR-18；**规格 §4.5～4.6**（`asyncio.create_task`、快照、`MEMORY_KEEPER_FAILED`）  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

从 **`workflow.py`** 移除 **`memory_keeper` 图节点**，**`short_term` → `router`**。**`generator.py`** 在产出用户可见回复（含 **`TASK_CLARIFY`** 与合并成果路径）后调用 **`schedule_memory_keeper_after_reply(scope_id, messages)`**，内部 **`asyncio.get_running_loop().create_task(run_memory_keeper_safe(snapshot))`**。**`memory_keeper.py`**：消息序列化为不可变快照；**`run_memory_keeper_safe`** 内 **`try/except`**，失败记录 **`MEMORY_KEEPER_FAILED`**；写库逻辑收敛为 **`run_memory_keeper_persist`**；**`MemoryKeeper`** 默认 DB 路径走 **`Settings.get_user_profiles_db_path()`**。**`memory_keeper_node`** 保留为兼容/手工 **`await`** 入口（返回 `{}`）。**`main.py`** 去掉已下线节点的 status 文案。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/workflow.py` | 修改 | 移除 L4 同步边 |
| `src/agent/nodes/generator.py` | 修改 | 回复后调度 L4 |
| `src/agent/nodes/memory_keeper.py` | 修改 | 快照、safe、schedule |
| `src/libs/base/settings.py` | 修改 | `get_user_profiles_db_path` |
| `src/agent/effective_constraint.py` | 修改 | `resolve_scope_id` → `get_scope_id`；DB 路径统一 |
| `tests/unit/test_effective_constraint_t011.py` | 修改 | mock `get_scope_id` |
| `main.py` | 修改 | STATUS_MAP |
| `docs/开发计划.md` | 修改 | T-012 |

### 规格对齐要点

- [§4.5] 回复就绪后异步任务；异常不挡主回复；日志 **`MEMORY_KEEPER_FAILED`**。  
- [§4.6] L4 不再阻塞 router 前序。  

### 规格偏差（若有）

当轮 **`memory_state.short_term_constraints`** 不再由 L4 同步回写 checkpoint（T-010 前序 **`short_term` 节点**仍负责 L3）；DB 短期状态下一轮到 **C**。

### 遗留问题

- [ ] 高频连发时 L4 与下一轮 **C** 的竞态可观测性（**T-028**）。  

### 关联

前置：T-011 ✓  
后续：T-013、T-014、T-028  
测试覆盖：`pytest tests/unit`（47 passed）

---

## [DEV-015] MCP 检索传入统一 **C**（T-015）

**类型**：`功能开发`  
**编号**：T-015  
**对应规格**：FR-11，FR-20；**规格 §5.1～§5.4**（检索增强与硬过滤）  
**里程碑**：M3  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

**`SearchRecipesService.execute`** 增加可选参数 **`effective_constraint`**（与 **`build_effective_constraint`** 产物同形）：命中时对 RAG 候选附带 **`content`**，调用 **`filter_recipes_by_hard_exclusions`**（与 Agent 侧 §5.4 同源），返回前去掉 **`content`** 字段；响应增加 **`effective_constraint_applied`**。**未传 **C** 时保留原 **`dietary_restrictions`** 粗过滤逻辑（兼容旧 MCP 调用）。**`src/mcp/server.py`** `search_recipes` 的 **`inputSchema`** 增加 **`effective_constraint`**、默认 **`top_k`=10**。**`researcher`**：**`search_recipes`** 传入 **`effective_constraint=effective_c`** 与 **`top_k=15`**；移除本轮重复的离线 **`filter_recipes_by_hard_exclusions`**（由 MCP 路径统一执行）。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/mcp/tool.py` | 修改 | **C** 分支与 §5.4 |
| `src/mcp/server.py` | 修改 | 工具契约 |
| `src/agent/nodes/researcher.py` | 修改 | MCP 参数 |

### 规格对齐要点

- [FR-11 / FR-20] 检索侧按同一 **`hard_exclusions`** 约束候选。  
- [§5.4] 与 **`effective_constraint.filter_recipes_by_hard_exclusions`** 行为一致。  

### 规格偏差（若有）

无。

### 遗留问题

- [ ] **`get_recipe_source`** 仍以菜名为键；全文阶段 **R** 仍以 **T-016** 为准。  

### 关联

前置：T-011 ✓  
后续：T-016、T-019  
测试覆盖：本轮按约定未执行 pytest  

---

## [DEV-016] 短期状态 TTL 与每轮清理（T-013）

**类型**：`功能开发`  
**编号**：T-013  
**对应规格**：FR-13；**规格 §3.4**（`expires_at`、查询过滤）  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

新增 **`src/agent/short_term_ttl.py`**：**`run_short_term_ttl_cleanup(scope_id)`** 在配置开启时调用 **`UserProfileManager.purge_expired_states(scope_id)`**，物理删除本 **SCOPE_ID** 下已过期或已失活的 **`user_short_term_states`** 行。**`short_term_constraints_node`** 在 **`build_l3_memory_patch`** 之前执行清理。**`Settings`**：**`get_short_term_ttl_days`**、**`should_purge_short_term_expired_on_turn`**。**`config/setting.yaml`**：**`memory.short_term_ttl.default_days`** / **`purge_expired_on_turn`**。**`MemoryKeeper`** 写入短期状态时使用配置的 **`ttl_days`**。**`workflow.py`** 注释对齐。

### 变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/agent/short_term_ttl.py` | 新增 | T-013 清理入口 |
| `src/agent/nodes/short_term.py` | 修改 | L3 前调用清理 |
| `src/libs/base/settings.py` | 修改 | TTL / purge 开关 |
| `src/agent/nodes/memory_keeper.py` | 修改 | `add_short_term_state` 传入 TTL |
| `config/setting.yaml` | 修改 | `memory.short_term_ttl` |
| `src/agent/workflow.py` | 修改 | 注释 |
| `docs/开发计划.md` | 修改 | T-013 |

### 规格对齐要点

- [FR-13] 短期状态具备可配置 TTL 与周期性物理清理，减轻对推荐的永久污染。  
- [§3.4] 与 **`expires_at`**、懒标记逻辑互补（purge 为显式删除）。  

### 规格偏差（若有）

**`memory_state.short_term_constraints`（L3）** 仍为会话内字符串列表，无逐条 TTL；失效主要靠会话结束与新轮关键词覆盖。

### 遗留问题

- [ ] L3 与 DB 短期条件的显式对齐/过期策略可作为后续增强。  

### 关联

前置：T-012 ✓  
后续：T-014（见 [DEV-017]）  
测试覆盖：按约定本轮未执行 pytest  

---

## [DEV-017] 画像库幂等、显式修正与 SCOPE 迁移（T-014 / IR-05）

**类型**：`功能开发`  
**编号**：T-014  
**对应规格**：**IR-05**；**规格 §3.2、§3.3**；**FR-12**（被动/显式）  
**里程碑**：M2  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

- **`UserProfileManager.apply_long_term_patch(user_id, patch, intent_type)`**：集中实现 **§3.3**（被动并集去重、显式按**出现字段**替换；`dietary_target` 显式可清空；口味显式按 `like`/`dislike` 子键替换）。**归一化比较**后无变化则**跳过 UPSERT**（幂等）。  
- **遗留 `user_id=default_user` → 当前 `household.default_id`**：在三张相关表上 **幂等迁移**；与目标主键冲突时 **删遗留行**（见实现注释）。  
- **构造时 `scope_id_for_migration=`**：`MemoryKeeper`、`build_effective_constraint` 读库路径、`short_term_ttl`、`mcp` 的 `UserProfileManager` 均传入 SCOPE，保证**首读前**即完成迁移。  
- **`MemoryKeeper`**：显式修正使用 **`model_dump(exclude_unset=True)`**；写库走 `apply_long_term_patch`。

**短期表 TTL** 仍由 T-013 配置与 `add_short_term_state` 负责；本任务覆盖 IR-05 中**长期行策略**与**读路径一致**。

### 变更文件（主要）

| 文件 | 说明 |
|------|------|
| `src/libs/base/user_profiles.py` | `apply_long_term_patch`、`_migrate_legacy_scope`、归一化比较 |
| `src/agent/nodes/memory_keeper.py` | 委托 `apply_long_term_patch`；显式 `exclude_unset` |
| `src/agent/effective_constraint.py`、`src/agent/short_term_ttl.py`、`src/mcp/server.py` | `scope_id_for_migration` |

### 关联

前置：T-012 ✓、T-013 ✓  
后续：—  
测试覆盖：本轮未执行 pytest  

---

## [DEV-018] 阶段一锁定与阶段二权威 **R**（T-016 / §5.1～5.2）

**类型**：`功能开发`  
**编号**：T-016  
**对应规格**：**FR-21**；**规格 §5.1～5.3**  
**里程碑**：M3  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

- **§5.1**：`stage1_high_confidence` + **`Settings.get_retrieval_top2_relative_gap`**（`config/setting.yaml` **`retrieval.confidence.top2_relative_gap`**）；歧义分支仍 **不** 调用阶段二。  
- **§5.2**：**`resolve_authoritative_structured_recipe`** — 仅以 **`get_recipe_source(recipe_name=锁定 title)`** 得到路径后 **`open` 全文 Markdown**，再 **`StructuredRecipe`** 抽取；失败映射 **`RECIPE_SOURCE_NOT_FOUND`** / **`RECIPE_PARSE_FAILED`**（**`error_state_from_expert_payloads`** 优先读 **`error_code`**）。  
- **状态**：成功写入 **`recipe_title_locked`**、**`recipe_parser_version`**（常量 **`llm_structured_v1`**，§5.3）、**`selected_recipe_id`** = 解析所用 **`recipe_file_ref`**。  

### 变更文件（主要）

| 文件 | 说明 |
|------|------|
| `src/agent/nodes/researcher.py` | T-016 核心逻辑 |
| `src/libs/base/settings.py` | `get_retrieval_top2_relative_gap` |
| `config/setting.yaml` | `retrieval.confidence` |
| `src/agent/state_sync.py` | `recipe_parser_version`、`error_code` |

### 关联

前置：T-015 ✓  
后续：T-017（见 [DEV-019]）  
测试覆盖：本轮未执行 pytest  

---

## [DEV-019] 菜谱歧义澄清（T-017 / FR-22）

**类型**：`功能开发`  
**编号**：T-017  
**对应规格**：**FR-22**；**规格 §5.1**（有限候选 + 不调用阶段二）  
**里程碑**：M3  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

- **`build_ambiguity_candidates`**（`src/agent/recipe_ambiguity.py`）：对检索结果 **按 title 去重**、截断至 **`retrieval.ambiguity.max_candidates`**（默认 6），项含 **`title` / `score` / `rank`**。  
- **`researcher`** 歧义分支写入结构化 **`recipe_candidates`**，**`clarification_kind`=`recipe_pick`**，载荷 **`ambiguity_candidate_count`**。  
- **`control_state` / `materialize_runtime_bundle`**：同步 **`clarification_kind`**、**`clarify_error`**（选菜失败后再提示）。  
- **`clarify_resolver`**：序号解析保留；菜名改为 **打分择优**（完整 > 前缀 > 子串），降低误匹配。  
- **`generator`**：`invalid_choice` 时追加说明；展示文案对齐「相关性排序」；回复后 **清除一次性 `clarify_error`**；成功解析后 clarify **清空 `clarification_kind`**。

### 变更文件（主要）

| 文件 | 说明 |
|------|------|
| `src/agent/recipe_ambiguity.py` | 新增 |
| `src/agent/nodes/researcher.py`、`generator.py`、`clarify_resolver.py` | T-017 |
| `src/agent/state_sync.py`、`config/setting.yaml`、`src/libs/base/settings.py` | 配置与切片 |

### 关联

前置：T-016 ✓  
后续：T-018（见 [DEV-020]）  
测试覆盖：本轮未执行 pytest  

---

## [DEV-020] 检索无结果降级与软约束重试（T-018 / FR-24）

**类型**：`功能开发`  
**编号**：T-018  
**对应规格**：**FR-24**；**规格 §5.4**（硬过滤后为空同属「无候选」处理口径）  
**里程碑**：M3  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

- **`effective_constraint_has_retryable_soft_signals`** / **`relaxed_effective_constraint_for_search_retry`**：`scope_id` 与 **`hard_exclusions`** 不变，清空 **`soft_*`、`temporal_conditions`、`dietary_target`、`summary_snippet`**，用于第二轮 query 增强与 MCP **`effective_constraint`**（§5.4 仍生效）。  
- **`researcher_node`**：首轮 `recipes` 为空且配置 **`soft_retry_max` > 0** 且存在可放宽软信号时，循环重试（默认 1 次）；成功则继续原有置信度 / 歧义分支。  
- **降级话术**：若已执行放宽仍空，生成说明性 **`degraded_reply`**；**`expert_payloads`** 增加 **`error_code`=`RECIPE_SEARCH_EMPTY`**、**`recipe_search_soft_retry_attempted`**。  
- **`config/setting.yaml`**：**`retrieval.empty_search.soft_retry_max`**；**`Settings.get_recipe_search_soft_retry_max`**（上限 5）。

### 变更文件（主要）

| 文件 | 说明 |
|------|------|
| `src/agent/effective_constraint.py` | 软约束判定与放宽副本 |
| `src/agent/nodes/researcher.py` | 空结果重试与话术 |
| `config/setting.yaml`、`src/libs/base/settings.py` | 配置 |

### 关联

前置：T-015 ✓  
后续：T-019（见 [DEV-021]）  
测试覆盖：本轮未执行 pytest  

---

## [DEV-021] MCP §2 JSON 契约与错误分支（T-019 / IR-02）

**类型**：`功能开发`  
**编号**：T-019  
**对应规格**：**IR-02**；**规格 §2.2～2.4**  
**里程碑**：M3  
**状态**：`已完成`  
**日期**：2026-05-06  

### 做了什么

- **`src/mcp/protocol.py`**：`mcp_validation_error`、`normalize_search_recipe_item` / **`normalize_search_recipes_success_body`**（§2.2：`recipes[]` 仅 **`id`/`title`/`score`**；可选 **`effective_constraint_applied`**）、**`is_mcp_error_response`**（Agent 分支）。  
- **`server.py`**：`search_recipes` / `get_recipe_source` 入参 **非空字符串** 校验；工具列表 **`top_k` 默认 5**（对齐 §2.2）。  
- **`SearchRecipesService`**：空 **`query`** → 校验错误包络；成功响应走归一化；**`execute` 默认 `top_k=5`**。  
- **`RecipeSourceService`**：§2.3 语义注释；空 **`recipe_name`** 由服务端校验或 **`ValueError`**（直接调用时）。  
- **`researcher._call_mcp_tool`**：**JSONDecodeError** → `status`/`error`；空响应带 **`status`**；检索分支用 **`is_mcp_error_response`**（含软重试）。

### 变更文件（主要）

| 文件 | 说明 |
|------|------|
| `src/mcp/protocol.py` | 新增 |
| `src/mcp/server.py`、`src/mcp/tool.py` | 校验与成功体 |
| `src/agent/nodes/researcher.py` | 解析与失败判定 |

### 关联

前置：T-015 ✓  
后续：—  
测试覆盖：本轮未执行 pytest  

---

