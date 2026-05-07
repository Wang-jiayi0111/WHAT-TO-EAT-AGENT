# WHAT-TO-EAT-AGENT 测试报告

项目：WHAT-TO-EAT-AGENT  
规格基线：docs/规格设计.md v2.4 · docs/项目说明.md（SRS v1.7）  
维护者：测试 Agent  
格式：v1.0  

> 只追加，不修改历史记录。缺陷编号由测试 Agent 分配，从 BUG-001 开始。

---

## 测试进度总表

| 任务编号 | 功能描述 | 测试状态 | 关联 BUG | 复审状态 | 最后更新 |
|---------|---------|---------|---------|---------|---------|
| T-001 | 建立测试夹具与快照用例 | ✅ 通过（已完成，基线） | — | — | 2026-05-06 |
| T-002 | 意图分流 + §1.3 步 5 静默缺口预计算（logistics） | ✅ 通过 | BUG-001 | 已关闭（见 [TR-010]） | 2026-05-06 |
| T-003 | 任务队列 `task_stack` 消费与调度 | ✅ 通过 | — | — | 2026-05-06 |
| T-004 | 路由节点结构化输出（FR-01） | ✅ 通过 | — | — | 2026-05-06 |
| T-005 | 低置信阈值 `clarify_threshold`（FR-03 / §8） | ✅ 通过 | — | — | 2026-05-06 |
| T-006 | 元意图 help / 超范围 / `dietary_advice` / `recipe_adopt`（FR-02） | ✅ 通过 | — | — | 2026-05-06 |
| T-007 | 多意图 FR-50 排序（`sort_intents_by_fr50`） | ✅ 通过 | — | — | 2026-05-06 |
| T-008 | 次意图合并答复（`generator` FR-52） | ✅ 通过 | — | — | 2026-05-06 |
| T-030 | 方案 A 七切片 AgentState（§1.2.0～1.2.1） | ✅ 通过 | — | — | 2026-05-06（[TR-011]） |
| T-031 | 槽位归一、`missing_slots`、`apply_slot_guards`（§11） | ✅ 通过 | — | — | 2026-05-06（[TR-012]） |
| INT-LLM | 集成：真实 LLM 意图识别（`IntentClassifier` 端到端） | ✅ 通过 | — | — | 2026-05-06（[TR-013]） |
| T-009 | L2 摘要与业务清场解耦（§4.2） | ✅ 通过 | — | — | 2026-05-06（[TR-014]） |
| T-010 | L3 当轮约束 + 检索 query 增强（FR-17 / §4.3） | ✅ 通过 | — | — | 2026-05-06（[TR-015]） |
| T-011 | 有效约束 **C** 合并 + §5.4 硬过滤 | ✅ 通过 | — | — | 2026-05-06（[TR-016]） |
| T-012 | L4 MemoryKeeper 异步与安全壳（§4.5） | ✅ 通过 | — | — | 2026-05-06（[TR-017]） |
| T-013 | 短期状态 TTL / 懒清理 / purge（FR-13 / §3.4） | ✅ 通过 | — | — | 2026-05-06（[TR-018]） |
| T-014 | 长期画像 patch / IR-05 / SCOPE 迁移 | ✅ 通过 | — | — | 2026-05-06（[TR-019]） |
| INT-M2 | 记忆子系统模块间集成（L3→**C**→query→§5.4；T-013 清理；T-014 库→C） | ✅ 通过 | — | — | 2026-05-07（[TR-020]） |
| T-015 | 检索链路传入统一 **C**（`researcher` / `SearchRecipesService` / MCP） | ✅ 通过 | — | — | 2026-05-07（[TR-021]） |
| T-016 | 高置信锁定 + §5.2 权威 **R**（`resolve_authoritative_structured_recipe` / 错误码） | ✅ 通过 | — | — | 2026-05-07（[TR-022]） |
| T-017 | 菜谱歧义：有限候选、`clarify_resolver`、`clarify_error`、generator 重问话术 | ✅ 通过 | — | — | 2026-05-07（[TR-023]） |
| T-018 | 无结果降级：软约束放宽重试、`RECIPE_SEARCH_EMPTY`、降级话术 | ✅ 通过 | — | — | 2026-05-07（[TR-024]） |
| T-019 | MCP 契约：`protocol` 归一、`SearchRecipesService` / `RecipeSourceService` | ✅ 通过 | — | — | 2026-05-07（[TR-025]） |
| INT-M3 | 菜谱子系统 M3 模块间集成（**C**→query→§2.2；FR-24；歧义+澄清；高置信 **R**） | ✅ 通过 | — | — | 2026-05-07（[TR-026]） |
| INT-M4 | M4 库存与清单模块集成（§6～§7；**I**、扣减、补货、缺口缓存、overlay）；`tests/integration/test_m4_inventory_list_module.py` | ✅ 通过 | — | — | 2026-05-07（[TR-037]） |
| T-032 | `inventory` 表 `household_id` 迁移与 SCOPE 对齐（§6.2、§8）；单测 `tests/unit/test_t032_inventory_migration.py` | ✅ 通过 | — | — | 2026-05-07（[TR-027]） |
| T-020 | 库存快照 **I** → `inventory_state.inventory_snapshot`（FR-30 / §6.1 / §1.2.1）；单测 `tests/unit/test_t020_inventory_snapshot.py` | ✅ 通过 | — | — | 2026-05-07（[TR-028]） |
| T-033 | 补货预览/确认 §6.5、`add_preview`、`restock_confirm`；单测 `tests/unit/test_t033_restock_preview.py` | ✅ 通过 | BUG-002 | 已关闭（见 [TR-031]） | 2026-05-07（[TR-029] 初审；[TR-031] 复审） |
| T-021 | §6.3 `TASK_INV_COMMIT`、`recipe_use_confirmed`、菜名锚点；单测 `tests/unit/test_t021_inv_commit_section63.py` | ✅ 通过 | — | — | 2026-05-07（[TR-032]） |
| T-022 | 扣减/补货写失败显式反馈（FR-32 / §6.4、§6.5.5）；单测 `tests/unit/test_t022_inventory_write_feedback.py` | ✅ 通过 | — | — | 2026-05-07（[TR-034]） |
| T-023 | 购物缺口缓存 §7.3、`gap_delivery_mode`、`GAP_CACHE_MISS`；单测 `tests/unit/test_t023_gap_cache.py` | ✅ 通过 | — | — | 2026-05-07（[TR-035]） |
| T-024 | 清单 overlay、`list_action`、`mark_bought_items`（§7.4、FR-41/43）；单测 `tests/unit/test_t024_shopping_list_overlay.py` | ✅ 通过 | — | — | 2026-05-07（[TR-036]） |

---

## 验证记录

<!-- 测试 Agent 从此处开始追加验证记录，格式见 docs/dev_log_format.md 中的测试报告规范 -->

## [TR-001] T-001 功能验证

**验证任务**：T-001 建立核心路径 pytest 夹具与 `workflow` 路由快照用例（`tests/unit/test_workflow_routing_baseline.py`，锚定 `docs/规格设计.md` §10 / `workflow.py`）

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

在仓库根目录执行：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 2（`pytest.ini` 仅匹配 `test_*.py`） |
| `test_minimal_agent_state_fixture` | ✅ 通过 |
| `test_workflow_routing_matches_snapshot` | ✅ 通过 |

**说明**：`tests/unit/bm25_test.py`、`tests/unit/chroma_test.py` 为本地调试脚本（无 `test_*` 函数、依赖外部 DB），未纳入 pytest 收集，本次不作为自动化回归项。

### 测试用例执行情况

| 用例 | 描述 | 对应场景 / 依据 | 结果 |
|------|------|-----------------|------|
| TC-001 | 夹具最小状态：`task_stack` 为空、`recipe_candidates` 为空 | T-001 夹具语义 | ✅ 通过 |
| TC-002 | `route_by_task` / `route_after_research` / `route_after_clarify` / `route_after_generator` 与快照 JSON 一致 | NFR-05；规格 §10 编排目录 | ✅ 通过 |
| TC-003 | `TASK_INV_CHECK` 栈顶让位于 `TASK_SEARCH`（覆盖路由优先级） | 规格 §1.3 / 工作流边 | ✅ 通过 |

### 禁止行为与基线合规（通用检查）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `task_stack` 为任务队列名；禁用 `task_queue` | ✅ 合规 | `src` 下未发现 `task_queue` |
| 库存访问未使用 `thread_id` 作为键 | ✅ 合规 | `InventoryManager` 按食材 `name`；`workflow` 中 `thread_id` 仅用于 LangGraph checkpointer |
| L2 摘要节点是否误改菜谱业务字段 | ⚠️ 观察项 | `conversation_summary_node` 在 `task_stack` 为空时会写入不完整 `logistics_buffer`，与规格 §4.2「摘要不误清业务现场」及 T-009 目标存在偏差风险；未单独建 BUG（待 T-009 专项验收） |
| AgentState 七切片顶层结构 | ⚠️ 未达标（已知基线） | 当前仍为扁平 `AgentState` + `logistics_buffer`；开发计划 **T-030** 待实施 |
| `inventory_snapshot` 为规格 §1.2.1 字典型 **I** | ⚠️ 未达标（已知基线） | `LogisticsBuffer` 注解为 `List`；`logistics` 节点写入 `Dict`，形态与类型不一致；对齐依赖 **T-030 / T-020** |

### 缺陷列表

- 本次验证未登记新 BUG（未发现阻断 T-001 基线通过的缺陷）。

---

## [TR-002] T-002 功能验证

**验证任务**：T-002 静默缺口预计算（规格 §1.3 步 5 / §7.1），实现见 `src/agent/nodes/logistics.py`（`_apply_silent_gap_precalc` 等）；依据 `docs/开发计划.md`、DEV-002。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 6 |
| 全部用例 | ✅ 通过（约 5.7s） |

| 文件 | 用例数 | 说明 |
|------|--------|------|
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002；`LogisticsManager` 已 mock，不碰真实 `inventory.db` |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 路由快照回归 |

### 测试用例执行情况

| 用例 | 描述 | 对应规格 / 任务 | 结果 |
|------|------|-----------------|------|
| TC-101 | `_stable_r_fingerprint` 与 R 列表顺序无关 | §7.1 / gap_basis | ✅ 通过 |
| TC-102 | `_inventory_fingerprint` 对同一 I 稳定 | 缓存失效语义 | ✅ 通过 |
| TC-103 | 栈上无 `TASK_GAP_CALC` 时仍写入 `cached_shopping_gap`、`gap_basis`（含菜谱标题） | §1.3 步 5 静默预计算 | ✅ 通过 |
| TC-104 | `TASK_INV_COMMIT` 后仍执行静默预计算并刷新缓存 | R+I 就绪后预计算 | ✅ 通过 |
| TC-105～106 | T-001 路由快照（回归） | NFR-05；§10 | ✅ 通过 |

### 禁止行为与基线合规（抽样）

| 检查项 | 结果 |
|--------|------|
| `task_stack` / 禁用 `task_queue` | ✅（未回归） |
| 本轮未发现阻断 T-002 的新缺陷 | ✅ |

### 缺陷列表

- 未登记新 BUG。

---

## [TR-003] 全量自动化回归（T-001～T-003）

**验证任务**：在当前代码基线上执行 `tests/` 下全部 pytest 用例，覆盖 T-001 路由快照、T-002 静默缺口预计算、T-003 `task_stack` 工具函数。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

命令：`python -m pytest tests -v --tb=short`（工作目录：仓库根）

| 项目 | 结果 |
|------|------|
| 收集用例数 | 8 |
| 通过 / 失败 | 8 / 0 |
| 耗时（约） | 6.4s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |

### 禁止行为（抽样）

| 检查项 | 结果 |
|--------|------|
| `src` 内 `task_queue` | ✅ 未发现 |

### 缺陷列表

- 未登记新 BUG。

### 开发计划同步

`docs/开发计划.md` §3：`T-001`～`T-003` 行「测试状态」已为 **已完成**，本轮结论一致，无需修改。

---

## [TR-004] T-004 验证 + 全量回归（T-001～T-004）

**验证任务**：T-004 `router` 节点输出 `primary_intent`、`intents`、`confidence`、`needs_clarification`（FR-01），单测见 `tests/unit/test_router_structured_output.py`；并执行仓库内全部 pytest 回归。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 11 |
| 通过 / 失败 | 11 / 0 |
| 耗时（约） | 6.2s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_router_structured_output.py` | 3 | T-004 |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |

### T-004 用例摘要

| 用例 | 描述 | 结果 |
|------|------|------|
| — | 分类器返回完整 detail 时写入 FR-01 相关字段 | ✅ |
| — | `TASK_CLARIFY` 等待澄清时跳过 LLM | ✅ |
| — | 空 messages 返回安全默认值 | ✅ |

### 缺陷列表

- 未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-004**「测试状态」**待测试** → **已完成**。

---

## [TR-005] T-005 验证 + 全量回归（T-001～T-005）

**验证任务**：T-005 `Settings.get_intent_clarify_threshold`（`intent.confidence.clarify_threshold`，规格 §8）；单测 `tests/unit/test_settings_intent_threshold.py`。并执行全部 pytest 回归。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 13 |
| 通过 / 失败 | 13 / 0 |
| 耗时（约） | 5.6s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_settings_intent_threshold.py` | 2 | T-005 |
| `tests/unit/test_router_structured_output.py` | 3 | T-004 |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |

### T-005 用例摘要

| 用例 | 描述 | 结果 |
|------|------|------|
| `test_default_clarify_threshold_when_key_missing` | 缺省配置时默认阈值 0.55 | ✅ |
| `test_clarify_threshold_from_config` | `intent.confidence.clarify_threshold` 从 YAML 读取 | ✅ |

### 缺陷列表

- 未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-005**「测试状态」**待测试** → **已完成**。

---

## [TR-006] T-006 验证 + 全量回归（T-001～T-006）

**验证任务**：T-006 元意图直达回复（`GeneratorNode.handle_direct_reply`：help、out_of_scope、recipe_adopt、`dietary_advice` 委托）；单测 `tests/unit/test_meta_intent_replies.py`。并执行全部 pytest 回归。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 17 |
| 通过 / 失败 | 17 / 0 |
| 耗时（约） | 5.7s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_meta_intent_replies.py` | 4 | T-006 |
| `tests/unit/test_settings_intent_threshold.py` | 2 | T-005 |
| `tests/unit/test_router_structured_output.py` | 3 | T-004 |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |

### T-006 用例摘要

| 用例 | 描述 | 结果 |
|------|------|------|
| `test_handle_direct_reply_help` | `help` → 帮助话术 | ✅ |
| `test_handle_direct_reply_out_of_scope` | `out_of_scope` → 超范围话术 | ✅ |
| `test_handle_direct_reply_recipe_adopt` | `recipe_adopt` → 采纳提示 | ✅ |
| `test_handle_direct_reply_dietary_delegates` | `dietary_advice` → 委托主生成链路 | ✅ |

### 缺陷列表

- 未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-006**「测试状态」**待测试** → **已完成**。

---

## [TR-007] T-007 验证 + 全量回归（T-001～T-007）

**验证任务**：T-007 `intent_priority.sort_intents_by_fr50`（FR-50 多意图优先级）；单测 `tests/unit/test_intent_priority_fr50.py`。并执行全部 pytest 回归。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 20 |
| 通过 / 失败 | 20 / 0 |
| 耗时（约） | 6.1s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_intent_priority_fr50.py` | 3 | T-007 |
| `tests/unit/test_meta_intent_replies.py` | 4 | T-006 |
| `tests/unit/test_settings_intent_threshold.py` | 2 | T-005 |
| `tests/unit/test_router_structured_output.py` | 3 | T-004 |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |

### T-007 用例摘要

| 用例 | 描述 | 结果 |
|------|------|------|
| `test_recipe_search_before_inventory_check` | `recipe_search` 先于 `inventory_check` | ✅ |
| `test_profile_sync_first` | `profile_sync` 优先于其它示例意图 | ✅ |
| `test_stable_when_same_tier` | 同秩意图保持输入顺序 | ✅ |

### 缺陷列表

- 未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-007**「测试状态」**待测试** → **已完成**。

---

## [TR-008] T-008 验证 + 全量回归（T-001～T-008）及 T-030 回归暴露项

**验证任务**：执行仓库 `tests/` 下全部 pytest；覆盖 T-008 `tests/unit/test_generator_merged_replies.py`（FR-52 合并答复）；并对提示词中的通用项做静态抽查（`task_queue`、`task_stack`、§1.2.0 七切片顶层键）。

**验证时间**：2026-05-06

**最终结论**：❌ 有缺陷（2 例失败，登记 BUG-001；其余 23 例通过）

### 测试执行

命令：`python -m pytest tests -v --tb=short`（工作目录：仓库根）

| 项目 | 结果 |
|------|------|
| 收集用例数 | 25 |
| 通过 / 失败 | 23 / 2 |
| 耗时（约） | 8.2s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/test_generator_merged_replies.py` | 5 | T-008 |
| `tests/unit/test_intent_priority_fr50.py` | 3 | T-007 |
| `tests/unit/test_logistics_silent_gap.py` | 4 | T-002 |
| `tests/unit/test_meta_intent_replies.py` | 4 | T-006 |
| `tests/unit/test_router_structured_output.py` | 3 | T-004 |
| `tests/unit/test_settings_intent_threshold.py` | 2 | T-005 |
| `tests/unit/test_task_stack.py` | 2 | T-003 |
| `tests/unit/test_workflow_routing_baseline.py` | 2 | T-001 |

### 失败用例

| 用例 | 描述 | 结果 |
|------|------|------|
| `test_silent_precalc_writes_cached_gap_without_gap_calc_task` | 静默预计算写入缓存 | ❌ `KeyError: 'logistics_buffer'` |
| `test_silent_precalc_runs_after_inv_commit` | `TASK_INV_COMMIT` 后静默预计算 | ❌ 同上 |

**原因（测试侧结论）**：`logistics_manager_node`（`src/agent/nodes/logistics.py`）在 T-030 阶段改为 `return` **`recipe_state` / `inventory_state` 等切片补丁**（`runtime_bundle_to_slice_patches`），不再返回顶层 `logistics_buffer`；`tests/unit/test_logistics_silent_gap.py` 仍断言 `out["logistics_buffer"]`，与当前契约不一致。静默预计算逻辑仍在运行（日志可见「静默缺口预计算完成」）。

### T-008 用例摘要（全部通过）

| 用例 | 结果 |
|------|------|
| `test_merge_two_tasks_order_and_double_newline` | ✅ |
| `test_non_mergeable_token_kept_in_place` | ✅ |
| `test_summarize_consumes_and_appends_pending_tasks` | ✅ |
| `test_direct_reply_degraded_skips_llm` | ✅ |
| `test_duplicate_mergeable_occurrences_stacked_twice` | ✅ |

### 禁止行为与基线合规（抽查）

| 检查项 | 结果 |
|--------|------|
| `task_stack`；`src` 内禁用名 `task_queue`（代码路径） | ✅ 仅 `task_stack.py` 注释提及 `task_queue` |
| `AgentState` 七切片一级键 | ✅ `state.py` 含 `dialog_state`～`error_state` 与 `merge_slice` |
| 库存 `thread_id` 作键 | ✅ `src/libs/base` 下 inventory 相关未见 `thread_id` 作 WHERE 键 |

### 缺陷列表

- **BUG-001**：T-002 静默缺口单测未对齐 T-030 节点返回形态（P2，待修复）

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-002**「测试状态」**已完成** → **待修改**；**T-008** 维持 **已完成**（单测全绿）。

---

## [BUG-001] T-002 单测仍断言 `logistics_buffer`，与 logistics 节点切片返回不一致

**严重程度**：`P2-一般`

**所属任务**：T-030（契约变更）/ 验收用例归属 T-002

**违反规格**：NFR-05（基线回归）；规格 §1.2.0 演进阶段与 §10 编排一致性（间接）

**发现时间**：2026-05-06

**状态**：`已关闭`（复审见 [TR-010]）

### 问题描述

T-030 阶段 `logistics_manager_node` 返回 `recipe_state`、`inventory_state` 等切片更新，不再包含顶层 `logistics_buffer`。`tests/unit/test_logistics_silent_gap.py` 中两条用例仍访问 `out["logistics_buffer"]`，导致 `KeyError`，全量 pytest 无法绿。

### 复现步骤

1. 在仓库根执行：`python -m pytest tests/unit/test_logistics_silent_gap.py::test_silent_precalc_writes_cached_gap_without_gap_calc_task -v`
2. 同样执行 `test_silent_precalc_runs_after_inv_commit`

### 预期行为

针对 T-002 的自动化验收应断言 **`inventory_state`（或节点实际返回键）** 中的 `cached_shopping_gap`、`gap_basis` 等字段，与 `src/agent/state_sync.py` 中 `inventory_state_from_logistics_buffer` 约定一致。

### 实际行为

测试在读取 `out["logistics_buffer"]` 时抛出 `KeyError`。

### 根因分析（测试侧初步判断）

`src/agent/nodes/logistics.py` 文末 `return out` 已改为合并 `runtime_bundle_to_slice_patches`；单测未同步更新断言路径。

### 影响范围

- 影响场景：M1 基线回归、CI 中 `pytest tests`
- 影响任务：T-002 显示「待修改」直至单测与实现对齐

---

## [TR-009] BUG-001 修复验证（T-002 / T-030 切片契约）

**验证任务**：确认 `tests/unit/test_logistics_silent_gap.py` 以 `empty_agent_slices()` 与 `runtime_bundle_to_slice_patches` 构造输入（无顶层 `logistics_buffer`），并直接断言 `out["inventory_state"]` 中的 `cached_shopping_gap`、`gap_basis` 等字段。

**执行命令**：`python -m pytest tests/unit/test_logistics_silent_gap.py -q`；`python -m pytest tests/unit -q`

**结果**：4 passed；`tests/unit` 全量 25 passed。

**结论**：单测与 `logistics_manager_node` 的切片返回形态一致；BUG-001 关闭。

---

## [TR-010] BUG-001 复审（开发修复后再验证）

**验证任务**：对 BUG-001 原复现路径做回归；并执行 `tests/` 全量 pytest，确认未引入新问题。

**验证时间**：2026-05-06

**关联开发记录**：`docs/dev_log.md` [DEV-009]（切片返回、`tests/unit` 断言对齐）

### 【复审结论 BUG-001】

复现步骤验证：

1. `python -m pytest tests/unit/test_logistics_silent_gap.py::test_silent_precalc_writes_cached_gap_without_gap_calc_task -v` → ✅ 通过  
2. `python -m pytest tests/unit/test_logistics_silent_gap.py::test_silent_precalc_runs_after_inv_commit -v` → ✅ 通过  

回归检查：`python -m pytest tests -v --tb=short` → **25 passed**，约 **5.4s**；未发现新失败用例。

**结论**：BUG-001 **关闭** ✅

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-002**「测试状态」**待修改** → **已完成**。

---

## [TR-011] T-030 功能验证（方案 A 七切片与访问器）

**验证任务**：T-030 **方案 A**——`AgentState` 一级七切片 + `active_user_id`；`get_runtime_bundle` / `runtime_bundle_to_slice_patches`；移除顶层 `logistics_buffer`（**规格 §1.2.0～1.2.1**；`docs/dev_log.md` [DEV-009]）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过（自动化全绿 + 静态验收项无违规；L2 与 §4.2 仍为观察项，见下表）

### 测试执行（自动化）

命令：`python -m pytest tests -v --tb=short`（仓库根）

| 项目 | 结果 |
|------|------|
| 收集用例数 | 25 |
| 通过 / 失败 | 25 / 0 |
| 耗时（约） | 5.3s |

**说明**：当前无独立文件名 `test_t030*.py`；T-030 由 **T-001 夹具**（`conftest.make_minimal_agent_state` + `empty_agent_slices` + `runtime_bundle_to_slice_patches`）、**T-002** `test_logistics_silent_gap`（切片断言）、**workflow 基线**（`get_runtime_bundle`）等共同覆盖。

### 测试用例执行情况（T-030 映射）

| 用例 | 描述 | 对应规格 / 任务 | 结果 |
|------|------|-----------------|------|
| TC-T030-01 | `empty_agent_slices()` 含且仅含 7 个切片键 | §1.2.0 | ✅（脚本校验） |
| TC-T030-02 | `runtime_bundle_to_slice_patches(make_logistics_buffer())` 产出 `recipe_state` / `inventory_state` / `control_state` 等补丁 | §1.2.0～1.2.1 | ✅（脚本校验） |
| TC-T030-03 | 全仓库 `tests/` pytest 回归 | NFR-05 | ✅ 25/25 |

### 禁止行为与基线合规（通用检查）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `AgentState` 使用七切片结构（`dialog_state`～`error_state`） | ✅ | `src/agent/state.py` |
| `AgentState` TypedDict **无** `logistics_buffer` 键 | ✅ | `state.py` 内 `grep` 无匹配 |
| `task_stack` 唯一；业务代码禁用 `task_queue` | ✅ | `src/**/*.py` 仅 `task_stack.py` 文档串提及 `task_queue` |
| `inventory_snapshot` 字典型 **I**（归一化路径） | ✅ | `state_sync._normalize_inventory_snapshot`；夹具中列表形态经补丁进入切片后可被消费 |
| L2 摘要节点是否误清业务切片（`recipe_state` 等） | ⚠️ 观察项 | `conversation_summary_node` 在 `task_stack` 为空时合并 `runtime_bundle_to_slice_patches(empty_runtime_bundle())`，会重置多切片；与 **FR-14 / §4.2** 及计划 **T-009** 专项验收相关；**本轮不登记新 BUG**（与 [TR-001] 观察一致） |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

`docs/开发计划.md` §3：**T-030**「测试状态」已为 **已完成**，与本轮结论一致，**无需修改**。

---

## [TR-012] T-031 功能验证（槽位 §11.2～11.5 与路由守卫）

**验证任务**：T-031——`slot_filling.py` 归一与 `compute_missing_slots`；`router.apply_slot_guards_to_task_stack`；`IntentResult.slots` / `missing_slots` 与 `intent_prompt.md` 契约（**规格 §11**；`docs/dev_log.md` [DEV-010]）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过（pytest 全绿 + 手工脚本覆盖核心槽位与映射；**未新增仓库单测**，与 DEV-010 说明一致）

### 测试执行（自动化）

命令：`python -m pytest tests -v --tb=short`

| 项目 | 结果 |
|------|------|
| 收集用例数 | 25 |
| 通过 / 失败 | 25 / 0 |
| 耗时（约） | 5.4s |

**与 T-031 间接相关的既有单测**：`tests/unit/test_router_structured_output.py`（`slots` / `missing_slots` 透传）；未覆盖 `compute_missing_slots` 全分支。

### 测试用例执行情况（手工脚本 + 抽查）

在仓库根执行一次性校验（导入 `tests.conftest.make_minimal_agent_state`、`IntentClassifier`、`slot_filling`）：

| 用例 | 描述 | 对应规格 / 任务 | 结果 |
|------|------|-----------------|------|
| TC-T031-01 | `recipe_search` 且无 `recipe_query`/`recipe_name`/食材 → `missing_slots` 含 `recipe_search_anchor` | §11.5 | ✅ |
| TC-T031-02 | 有上述缺失时 `apply_slot_guards_to_task_stack` 去掉 `TASK_SEARCH`、队首插入 `TASK_CLARIFY`，保留未阻塞意图任务 | §11.5、裁剪 | ✅ |
| TC-T031-03 | 同轮 `recipe_search`+`shopping_list` 且仅有 `recipe_name` 锚点、无 **R** → 不追加 `shopping_list_context` | DEV-010 豁免语义 | ✅ |
| TC-T031-04 | `entities.amounts` → `slots.restock_items` 行结构 | §11.2 | ✅ |
| TC-T031-05 | `merge_slots` 对值为 `None` 的键不覆盖基槽 | — | ✅ |
| TC-T031-06 | `IntentClassifier.INTENT_TASK_MAPPING` 的意图键 ⊆ `IntentResult.intents` 的 Literal 集合 | §11.3～11.4 | ✅ |

### 文档与 Prompt 抽查

| 检查项 | 结果 |
|--------|------|
| `intent_prompt.md` 含 `slots` / `missing_slots` 与 §11.2 说明 | ✅ |
| 规范码 `recipe_search_anchor` 与常量 `MISSING_RECIPE_SEARCH_ANCHOR` 一致 | ✅ |

### 禁止行为与基线合规

| 检查项 | 结果 |
|--------|------|
| `task_stack` 守卫不引入 `task_queue` | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 遗留与建议（非阻塞）

- 建议在后续迭代为 `slot_filling.py` 增加 **`tests/unit/test_slot_filling.py`**，固化 §11.5 边界（`inventory_commit`、`recipe_adopt`、`profile_sync` 等），减少对手工脚本的依赖。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-031**「测试状态」**待测试** → **已完成**。

---

## [TR-013] 集成：真实 LLM 意图识别（`tests/integration/test_intent_recognition_llm.py`）

**验证任务**：在启用真实大模型调用的情况下，对 **`IntentClassifier.get_intent_details`**（与 `router` 同源：`intent_prompt.md` + 结构化 `IntentResult` + FR-50 排序 + T-031 槽位/守卫）进行**集成验收**；覆盖单意图、**多意图**（如 `recipe_search`+`shopping_list`）、元意图及与 prompt **Example 1 / 3 / 5 / 7** 对齐的话术。

**验证时间**：2026-05-06

**最终结论**：✅ 通过（本机执行：**12 passed**，约 **161s**；依赖 `config/setting.yaml` 中 LLM 可用）

### 测试执行

**前置**：已配置可用的 LLM（如 DashScope/OpenAI 等，与项目 `Settings` / `LLMFactory` 一致）。

```powershell
cd <仓库根>
$env:WHAT_TO_EAT_RUN_LLM_INTENT = "1"
# 可选：$env:WHAT_TO_EAT_INTENT_REPORT = "logs/intent_llm_report.json"
# 可选：$env:WHAT_TO_EAT_INTENT_LLM_JUDGE = "1"
python -m pytest tests/integration/test_intent_recognition_llm.py -v --tb=short
```

| 项目 | 结果（本轮实测） |
|------|------------------|
| 收集用例数 | 12 |
| 通过 / 失败 / 跳过 | 12 / 0 / 0 |
| 耗时（约） | 161.4s（约 2m41s） |

**说明**：未设置 `WHAT_TO_EAT_RUN_LLM_INTENT=1` 时，本文件内用例 **全部 skip**（不计入上述通过数）；CI 默认不跑真实 LLM，避免密钥与费用问题。

### 测试用例执行情况（用例 ID 与脚本中 `INTENT_LLM_CASES` 一致）

| 用例 ID | 话术要点 | 验收要点（摘要） | 结果 |
|---------|----------|------------------|------|
| ex01_inventory_check_meat | 「冰箱里还有肉吗？」 | 契约 + 主意图/意图含 `inventory_check`；任务栈命中库存或澄清/直达 | ✅ |
| ex03_inventory_commit_done | 「刚才的清蒸鱼做好了。」 | 契约 + `inventory_commit`；任务含扣减或澄清等 | ✅ |
| ex05_inventory_add_restock | 超市购入多品 | 契约 + `inventory_add`；任务含补货或澄清等 | ✅ |
| ex07_vague_search_and_shopping | 「随便推荐…再看看缺啥要买」 | **多意图**：`intents` 必含 `recipe_search` 与 `shopping_list`；澄清/缺槽路径 | ✅ |
| search_named_dish | 点名红烧肉做法 | 契约 + `recipe_search`；`TASK_SEARCH` 或澄清 | ✅ |
| help_capabilities | 「你能做什么？」 | 契约 + help/闲聊；`TASK_DIRECT_REPLY` | ✅ |
| out_of_scope_code | 写 Python 排序 | 契约 + 超范围/闲聊；直达回复 | ✅ |
| dietary_advice_cold | 感冒饮食注意 | 契约 + 营养建议/闲聊；直达回复 | ✅ |
| profile_peanut | 花生过敏记下 | 契约 + `profile_sync`；画像或澄清等 | ✅ |
| multi_add_search_list | 买猪肉+红烧肉+还差什么 | **多意图场景**（补货+搜菜+缺口）；至少含 `recipe_search` | ✅ |
| weak_chat | 天气闲聊 | 契约 + 闲聊/帮助；直达回复 | ✅ |
| test_intent_llm_write_report_json | 汇总写 JSON | 全量再跑一遍并校验契约；报告落盘（默认 pytest 临时目录） | ✅ |

### 与需求 / 任务的对应关系

| 需求或任务 | 本集成项覆盖说明 |
|------------|------------------|
| FR-01 | `primary_intent`、`intents`、`confidence`、`needs_clarification` 等结构化输出契约（脚本内 `assert_structural_contract`） |
| 规格 §11、`intent_prompt.md` | 意图标签合法性、`slots`/`missing_slots` 类型、§11.5 与澄清路径（`ex07_*`） |
| FR-50（多意图） | 模型输出多意图后由路由排序；用例 `ex07_*`、`multi_add_search_list` 覆盖多意图话术 |
| T-031 | 路由侧合并规则缺失与 `task_stack` 守卫后的可执行栈（间接随整条链路验证） |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

无单独 **T-xxx** 行对应「仅 LLM 集成」；已在 **§测试进度总表** 增加 **INT-LLM** 一行便于追溯。**T-004 / T-007 / T-031** 等既有「已完成」结论与本集成结论一致，未改 `docs/开发计划.md`。

---

## [TR-014] T-009 功能验证（L2 `conversation_summary_node` 与 §4.2）

**验证任务**：T-009 / [DEV-011]——L2 节点**仅**返回 `messages`、`conversation_summary`、`memory_state` 中摘要镜像；**不得**返回 `task_stack`、`recipe_state`、`inventory_state` 等业务键（**规格 §4.2**；**FR-14 / FR-16**）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -q --tb=no`（仓库根；未设置 `WHAT_TO_EAT_RUN_LLM_INTENT` 时集成用例 skip）

| 项目 | 结果 |
|------|------|
| 收集用例数 | 41 |
| 通过 / 失败 / 跳过 | 29 / 0 / 12 |
| 耗时（约） | 8.1s |

| 测试文件 | 用例数 | 关联任务 |
|----------|--------|----------|
| `tests/unit/t001-031/test_conversation_summary_l2.py` | 4 | T-009 |
| 其余 `tests/unit/t001-031/*.py` + `tests/integration/...` | 25 + 12 skip | T-001～T-008 等 |

### 测试用例执行情况（T-009）

| 用例 | 描述 | 对应规格 / 任务 | 结果 |
|------|------|-----------------|------|
| `test_l2_empty_messages_returns_empty` | 无 messages 返回 `{}` | §4.2 边界 | ✅ |
| `test_l2_under_compress_threshold_no_llm_preserves_business_fields_untouched` | 短对话不触发压缩、不调用 LLM；返回键不含业务切片 | §4.2 | ✅ |
| `test_l2_compress_path_mocked_does_not_return_business_keys` | `maybe_compress` mock 触发压缩路径；返回不含 `task_stack` / `inventory_state` | §4.2 | ✅ |
| `test_l2_on_failure_returns_empty` | 压缩异常时返回 `{}` | 健壮性 | ✅ |

### 回归与夹具修复（T-001）

| 项 | 说明 |
|----|------|
| 路由快照路径 | `test_workflow_routing_baseline.py` 在 `tests/unit/t001-031/` 下时，`_SNAPSHOT` 已改为指向 **`tests/snapshots/workflow_routing_baseline.json`**（三级 `parent`），修复 `FileNotFoundError`，**T-001** 快照用例恢复绿。 |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-009**「测试状态」**待测试** → **已完成**。

---

## [TR-015] T-010 功能验证（L3 当轮约束与 `augment_query_for_search`）

**验证任务**：T-010 / [DEV-012]——`l3_short_term` 规则抽取与 `merge_short_term_constraints`；`build_l3_memory_patch` / `short_term_constraints_node` 仅写 `memory_state`；`researcher` 使用的 **`augment_query_for_search`** 将 L3 与 `active_constraints` 并入检索 query（**FR-17**；**规格 §4.3**）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -q --tb=no`（未设置 `WHAT_TO_EAT_RUN_LLM_INTENT`）

| 项目 | 结果 |
|------|------|
| 全库用例 | 37 passed，12 skipped |
| 耗时（约） | 5.4s |

| 测试文件 | 用例数 | 说明 |
|----------|--------|------|
| `tests/unit/t001-031/test_l3_short_term.py` | 8 | T-010；无真实 LLM / 无 MCP |

### 测试用例摘要

| 用例 | 内容 | 结果 |
|------|------|------|
| 关键词抽取 | 含「感冒」「清淡」用户句命中默认规则 | ✅ |
| 合并去重 | `merge_short_term_constraints` 顺序与去重 | ✅ |
| `latest_user_text` | 取最近 `HumanMessage` | ✅ |
| `build_l3_memory_patch` | 有命中时写入 `short_term_constraints` 与 `memory_confidence`；无新信息时 `{}` | ✅ |
| `short_term_constraints_node` | 与 `build_l3_memory_patch` 结果一致 | ✅ |
| `augment_query_for_search` | 拼接 `memory_state` 中 L3 与 `active_constraints`；空 base query 时 `[饮食约束]` 前缀 | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-010**「测试状态」**待测试** → **已完成**。

---

## [TR-016] T-011 功能验证（`effective_constraint`：C 合并、query 增强、§5.4 过滤）

**验证任务**：T-011 / [DEV-013]——`build_effective_constraint`（注入 `profile` 避免读库）、`resolve_scope_id`、`augment_search_query`、`filter_recipes_by_hard_exclusions`（**规格 §3.5、§5.4**；**FR-10 / FR-11 / FR-19**）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -q --tb=no`（未设置 `WHAT_TO_EAT_RUN_LLM_INTENT`）

| 项目 | 结果 |
|------|------|
| 全库用例 | 47 passed，12 skipped |
| 耗时（约） | 9.2s |

| 测试文件 | 用例数 | 说明 |
|----------|--------|------|
| `tests/unit/test_effective_constraint_t011.py` | 10 | T-011；置于 **`tests/unit/`**；无 MCP / 无真实 LLM |

### 测试用例摘要

| 主题 | 内容 | 结果 |
|------|------|------|
| `resolve_scope_id` | `household.default_id` 优先，否则 `active_user_id` | ✅ |
| `build_effective_constraint` | 合并 L3、DB 短期、过敏原/口味/摘要截断（`profile` 注入） | ✅ |
| `augment_search_query` | **C** 与 `active_constraints` 拼入检索 query | ✅ |
| `filter_recipes_by_hard_exclusions` | 中文子串与 ASCII 大小写不敏感命中 title/snippet/content | ✅ |

### 说明

- `hard_exclusions` 使用 `_unique_strs(..., min_len=2)`：**单字符**食材码会被忽略；单测使用长度 ≥2 的过敏原（如 `peanut`），与实现一致。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-011**「测试状态」**待测试** → **已完成**。

---

## [TR-017] T-012 功能验证（L4 `schedule_memory_keeper` / `run_memory_keeper_safe`）

**验证任务**：T-012 / [DEV-014]——消息快照序列化、`build_memory_keeper_snapshot`；`run_memory_keeper_safe` 吞并 `run_memory_keeper_persist` 异常（**FR-18**；**规格 §4.5**）；`schedule_memory_keeper_after_reply` 在有/无事件循环下的行为。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -q --tb=no`

| 项目 | 结果 |
|------|------|
| 全库用例 | 53 passed，12 skipped |
| 耗时（约） | 7.6s |

| 测试文件 | 用例数 | 说明 |
|----------|--------|------|
| `tests/unit/test_memory_keeper_t012.py` | 6 | T-012；mock 持久化层，无真实 LLM 写库 |

### 测试用例摘要

| 用例 | 内容 | 结果 |
|------|------|------|
| `serialize` / 往返 | Human/AI 文本快照与 `messages_from_keeper_snapshot` | ✅ |
| `build_memory_keeper_snapshot` | `scope_id` + `messages` 形状 | ✅ |
| `run_memory_keeper_safe` | `run_memory_keeper_persist` 抛错时不向外抛出 | ✅ |
| `schedule_memory_keeper_after_reply` | 在异步上下文中调度并传入正确快照 | ✅ |
| 无运行中 loop | 同步调用不崩溃（跳过调度） | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-012**「测试状态」**待测试** → **已完成**。

---

## [TR-018] T-013 功能验证（`user_short_term_states` TTL）

**验证任务**：T-013 / **FR-13**、**§3.4**——`add_short_term_state`、`get_active_short_term_states`（懒清理）、`purge_expired_states`、`deactivate_short_term_state`。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行

- 文件：`tests/unit/test_user_profiles_ttl_t013.py`（6 条，临时 SQLite）

### 开发计划同步

`docs/开发计划.md` §3：**T-013** 测试状态 **已完成**（与本轮一致）。

---

## [TR-019] T-014 功能验证（`apply_long_term_patch`、IR-05、遗留 SCOPE 迁移）

**验证任务**：T-014 / [DEV-017]——`UserProfileManager.apply_long_term_patch`（passive / explicit）；幂等跳过 UPSERT；`scope_id_for_migration` 迁移 `default_user` 长期画像（**IR-05**；**§3.2、§3.3**）。

**验证时间**：2026-05-06

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：`python -m pytest tests -q --tb=no`

| 项目 | 结果 |
|------|------|
| 全库用例 | 66 passed，12 skipped |
| 耗时（约） | 22s |

| 测试文件 | 用例数 |
|----------|--------|
| `tests/unit/test_user_profiles_t014_long_term.py` | 7 |

### 测试用例摘要

| 主题 | 结果 |
|------|------|
| passive 并集、幂等（`last_updated` 不变） | ✅ |
| explicit 替换过敏原、清空 `dietary_target`、部分更新 `taste_tags` | ✅ |
| 迁移：仅长期表 `default_user` → scope | ✅ |
| 迁移：目标已存在时删除遗留行 | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-014**「测试状态」**待测试** → **已完成**。

---

## [TR-020] 集成：M2 记忆子系统模块间验收（`tests/integration/test_memory_stack_m2_integration.py`）

**验证任务**：在 T-009～T-014 单测之外，对记忆相关模块做**跨模块串联**回归：L3 约束抽取与 `memory_state` 合并 → `build_effective_constraint`（**C**）→ `augment_search_query` 与 `augment_query_for_search` → `filter_recipes_by_hard_exclusions`（**§5.4**）；`run_short_term_ttl_cleanup` 与临时库 **T-013** 物理清理；`apply_long_term_patch` 写入后 `get_user_profile` 再入 **C**（**T-014** / **IR-05** 读路径）。  
**不替代** 单测文件；**不覆盖** 完整 LangGraph 工作流（非 E2E）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/integration/test_memory_stack_m2_integration.py -q --tb=no
```

| 项目 | 结果 |
|------|------|
| 用例数 | 3 |
| 结果 | 3 passed |
| 耗时（约） | 2.6s（本机，供参考） |

| 用例 | 说明 | 覆盖 |
|------|------|------|
| `test_m2_pipeline_L3_to_C_to_queries_and_hard_filter` | 用户句 → `build_l3_memory_patch` → 注入 profile → **C** → 双路 query 增强 → 硬排除过滤 | T-010、T-011（串联） |
| `test_m2_T013_run_short_term_ttl_cleanup_purges_expired` | `Settings` mock 开启 purge；过期 `user_short_term_states` 行被删除 | T-013（清理入口 + 真 SQLite） |
| `test_m2_T014_long_term_patch_roundtrip_with_chain` | 临时库 `apply_long_term_patch` 后 `get_user_profile` → `build_effective_constraint` 的 `hard_exclusions` | T-014（写库→读→C） |

### 说明

- 测试文件位于 **`tests/integration/`**，与 `tests/unit/` 中单点验收区分；全库回归时 `pytest` 会一并收集（视 `pytest.ini` / 工作目录而定）。
- 中文菜名与 **hard_exclusions** 关键词需可互相匹配（本用例用「花生」与菜名中的「花生」子串，与 `filter_recipes_by_hard_exclusions` 实现一致）。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

- 不新增开发计划任务行；**INT-M2** 为对 **T-009～T-014** 的**集成层补充验收**，与各任务 [TR-014]～[TR-019] 并列可查。

---

## [TR-021] T-015 功能验证（检索链路统一 **C**）

**验证任务**：T-015 / **FR-11**、**FR-20**——`RecipeResearcher.search_recipes` 向 MCP 传入 `effective_constraint`；`SearchRecipesService.execute` 在传入 **C** 时按 §5.4 硬过滤并标记 `effective_constraint_applied`；`researcher_node` 检索分支将 `build_effective_constraint` 与 `scope_for_mcp` 贯通至 MCP，并把 **C** 写入 `memory_state.effective_constraint`。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/unit/test_t015_retrieval_effective_constraint.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 5 |
| 结果 | 5 passed |

**需求追溯**：FR-11，FR-20；实现见 `researcher.search_recipes`、`SearchRecipesService.execute`、MCP `search_recipes` 可选 `effective_constraint`（`docs/dev_log.md` [DEV-015]）。

### 测试用例与验收点

| 测试函数 | 验收点 |
|----------|--------|
| `test_search_recipes_includes_effective_constraint_in_mcp_args` | `RecipeResearcher.search_recipes` 调用 MCP 时参数包含 `effective_constraint` |
| `test_search_recipes_omits_constraint_key_when_none` | 未传 **C** 时不下发该字段 |
| `test_search_recipes_service_applies_hard_exclusions_section_54` | `SearchRecipesService.execute` 带 **C** 时 §5.4 硬过滤 + `effective_constraint_applied` |
| `test_merge_effective_constraint_into_memory_patch_writes_memory_state` | `memory_state.effective_constraint` 写入 |
| `test_researcher_node_forwards_c_to_search_recipes_and_memory` | `researcher_node` 检索分支将 **C** 传给 `search_recipes`，返回态含同一 **C** |

### 说明

- 未启动真实 MCP 子进程：`RecipeResearcher` 侧 mock `_call_mcp_tool`；`researcher_node` 侧 mock `RecipeResearcher`。
- 与 `tests/unit/test_effective_constraint_t011.py`（T-011）互补：T-011 侧重 **C** 合成与过滤函数；T-015 侧重检索边界与 **C** 在 researcher / MCP 服务层贯通。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-015**「测试状态」**待测试** → **已完成**。

---

## [TR-022] T-016 功能验证（高置信锁定与全文解析 **R**）

**验证任务**：T-016 / **FR-21**、**规格 §5.1～§5.2**——`stage1_high_confidence`（`retrieval.confidence.top2_relative_gap`）；高置信后仅锁定 title，**R** 经 `get_recipe_source` → 全文 `parse_recipe_content`（`resolve_authoritative_structured_recipe`）；`RECIPE_PARSER_VERSION`；失败分支 `RECIPE_SOURCE_NOT_FOUND`、`RECIPE_PARSE_FAILED`（与 §9 话术对齐的可恢复错误）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/unit/test_t016_high_confidence_structured_r.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 13 |
| 结果 | 13 passed |

### 测试用例与验收点

| 测试函数 | 验收点 |
|----------|--------|
| `test_stage1_high_confidence_*` | §5.1：单候选锁定；双候选相对分差与 gap |
| `test_coerce_mcp_recipe_path_variants` | MCP 路径统一 |
| `test_resolve_authoritative_*` | §5.2：`source_not_found` / `empty_r` / 成功路径 |
| `test_researcher_node_high_confidence_sets_parser_version_and_requirements` | 高置信：`recipe_parser_version`、`recipe_requirements`、`recipe_title_locked` |
| `test_researcher_node_low_confidence_ambiguous_branch` | 低置信：`ambiguous`、`recipe_candidates` |
| `test_researcher_node_high_confidence_source_not_found` | `error_code == RECIPE_SOURCE_NOT_FOUND` |
| `test_researcher_node_high_confidence_parse_failed_empty_r` | `error_code == RECIPE_PARSE_FAILED` |

### 说明

- `researcher_node` 与 `RecipeResearcher` 全程 mock，不拉起 MCP 子进程。
- 实现见 `src/agent/nodes/researcher.py`（`RECIPE_PARSER_VERSION`、`resolve_authoritative_structured_recipe`、`_recoverable_recipe_fault`）。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-016**「测试状态」**待测试** → **已完成**。

---

## [TR-023] T-017 功能验证（多候选澄清 / FR-22）

**验证任务**：T-017 / **FR-22**、**规格 §5.1**——`build_ambiguity_candidates` 与 `retrieval.ambiguity.max_candidates`；低置信歧义分支 `clarification_kind=recipe_pick`、`ambiguity_candidate_count`；`clarify_resolver_node` 数字/菜名解析、成功推进 `TASK_SEARCH`、失败 `clarify_error=invalid_choice`；`GeneratorNode.handle_clarify` 对无效选择的补充提示。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/unit/test_t017_recipe_ambiguity_clarify.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 10 |
| 结果 | 10 passed |

### 测试用例与验收点

| 测试函数 | 验收点 |
|----------|--------|
| `test_build_ambiguity_candidates_*` | 去重、条数上限、空输入 |
| `test_parse_user_choice_*` | 序号、菜名子串、无法识别 |
| `test_clarify_resolver_*` | 成功锁定 title / 失败栈与标志 / 无候选短路 |
| `test_generator_handle_clarify_invalid_choice_prefix` | 无效选择时前缀话术 + 重列候选 |
| `test_researcher_low_confidence_sets_structured_candidates_and_clarification_kind` | 歧义上限、`recipe_pick`、展平 bundle 中候选标题列表 |

### 说明

- 运行时 bundle 中 `recipe_candidates` 经 `materialize_runtime_bundle_from_slices` 多为**标题字符串列表**（legacy 形状）；`build_ambiguity_candidates` 产出的 dict 在切片内保留完整字段。
- `researcher_node` 用例 mock MCP，不拉起子进程。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-017**「测试状态」**待测试** → **已完成**。

---

## [TR-024] T-018 功能验证（无结果说明与软约束重试 / FR-24）

**验证任务**：T-018 / **FR-24**——`effective_constraint_has_retryable_soft_signals`、`relaxed_effective_constraint_for_search_retry`（保留 `hard_exclusions` / `scope_id`）；`researcher_node` 首轮空结果后在 `get_recipe_search_soft_retry_max` 允许次数内用放宽 **C** 重试；仍空时 `expert_payloads.error_code=RECIPE_SEARCH_EMPTY`、`recipe_search_soft_retry_attempted` 与对应 `degraded_reply`；无软信号或 `soft_retry_max=0` 时不二次检索。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/unit/test_t018_fr24_empty_search_soft_retry.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 8 |
| 结果 | 8 passed |

### 测试用例与验收点

| 测试函数 | 验收点 |
|----------|--------|
| `test_effective_constraint_has_retryable_soft_signals_*` | 软提示 / 时间态 / 目标 / 摘要触发；仅 hard 不触发 |
| `test_relaxed_effective_constraint_keeps_hard_and_scope_clears_soft` | 放宽后软字段清空、硬排除与 scope 保留 |
| `test_researcher_empty_then_soft_retry_still_empty_sets_fr24_flags` | 二次 `search_recipes`、`RECIPE_SEARCH_EMPTY`、重试标记、长文案含「放宽」 |
| `test_researcher_empty_no_soft_signals_no_second_search` | 单次检索、短文案、无重试标记 |
| `test_researcher_soft_retry_max_zero_skips_retry` | `soft_retry_max=0` 不进入重试 |
| `test_researcher_second_search_returns_recipes_stops_retry_loop` | 放宽后命中结果则成功路径，无空检索错误码 |

### 说明

- `RecipeResearcher` mock，不拉起 MCP；`build_effective_constraint` 注入固定 **C**。
- 实现见 `src/agent/effective_constraint.py`、`src/agent/nodes/researcher.py`、`Settings.get_recipe_search_soft_retry_max`。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-018**「测试状态」**待测试** → **已完成**。

---

## [TR-025] T-019 功能验证（MCP JSON 契约 / IR-02 / §2）

**验证任务**：T-019 / **IR-02**、**规格 §2**——`mcp_validation_error`、`is_mcp_error_response`；`normalize_search_recipe_item` / `normalize_search_recipes_success_body` 仅暴露 `id`/`title`/`score`；`SearchRecipesService.execute` 空 query 校验、`top_k` 默认 **5**、带 **C** 时输出无 `content` 且含 `effective_constraint_applied`；`RecipeSourceService.execute` 空菜名校验与路径返回。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/unit/test_t019_mcp_contract.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 17 |
| 结果 | 17 passed |

### 说明

- 未导入 `src.mcp.server`（避免模块级初始化 RAG/Chroma）；`server.py` 中 `query` / `recipe_name` 非空字符串校验与 Service 层一致，由 Service 与 `protocol` 单测覆盖。
- `is_mcp_error_response` 对无 `recipes`、无 `status=error`、无 `error` 键的任意 dict 返回 **False**（与当前实现一致）。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已更新 `docs/开发计划.md` §3：**T-019**「测试状态」**待测试** → **已完成**。

---

## [TR-026] 集成：M3 菜谱子系统模块间验收（`tests/integration/test_recipe_stack_m3_integration.py`）

**验证任务**：在 **T-015～T-019** 单测之外，对 M3 菜谱链路做**跨模块串联**：`build_effective_constraint` → `augment_search_query` → `normalize_search_recipes_success_body`（§2.2，无 `content`）；`build_ambiguity_candidates` 与低置信上限一致；`researcher_node` 空结果 **FR-24** 软重试与 `RECIPE_SEARCH_EMPTY`；低置信歧义后 `clarify_resolver_node` 数字选择锁定 `selected_recipe_title`；单候选高置信经 `get_recipe_source` + 全文解析得到 **R** 与 `recipe_parser_version`。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

### 测试执行（自动化）

命令：

```text
python -m pytest tests/integration/test_recipe_stack_m3_integration.py -v --tb=short
```

| 项目 | 结果 |
|------|------|
| 用例数 | 5 |
| 结果 | 5 passed |

| 用例 | 覆盖 |
|------|------|
| `test_m3_chain_c_to_query_to_mcp_success_body_contract` | T-015、T-019 |
| `test_m3_build_ambiguity_candidates_aligns_with_low_confidence_cap` | T-017 |
| `test_m3_researcher_fr24_soft_retry_then_recipe_search_empty` | T-018 |
| `test_m3_ambiguous_researcher_then_clarify_numeric` | T-016、T-017 |
| `test_m3_high_confidence_authoritative_r_after_research` | T-016 |

### 说明

- **不启动** 真实 MCP 子进程：`RecipeResearcher` 全程 mock。
- **INT-M3** 为对 **T-015～T-019** 的集成层补充验收，与 [TR-021]～[TR-025] 并列可查。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

- 不新增开发计划任务行；里程碑 **M3 菜谱检索** 的集成验收以本 **[TR-026]** 与既有单测为准。

---

## [TR-027] T-032 功能验证（inventory `household_id` 迁移与 SCOPE）

**验证任务**：T-032 / [DEV-022]——`InventoryManager` 默认 `Settings.get_inventory_db_path()` 与 `get_scope_id()`；`_migrate_to_v62`（无表建 §6.2、已有 `household_id` 跳过、否则自 legacy 迁移）；读写 SQL 均带 `WHERE household_id = ?`；`ON CONFLICT(household_id, name)`；`LogisticsManager` 与 `InventoryManager` 路径/作用域一致；`integrity._initialize_inventory_db` 建表与业务一致（**规格 §6.2、§8**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例位置**：`tests/unit/test_t032_inventory_migration.py`（模块级字符串说明 = 测试计划与追溯；用例为 pytest 函数，**不**另建 `docs/` 下测试说明文件）。

### 测试过程信息（执行记录）

以下为本轮在仓库根目录（`F:\WHAT-TO-EAT-AGENT`）实际执行的命令与摘要输出，供审计与复跑对照。

1. **T-032 专项文件**

   ```text
   python -m pytest tests/unit/test_t032_inventory_migration.py -v --tb=short
   ```

   **结果**：收集 **4** 条；**4 passed**，约 **4.5s**；节点：`test_t032_tc001_empty_db_creates_section62_schema` … `test_t032_tc004_two_households_isolated_on_same_file` 均通过。

2. **全量回归**

   ```text
   python -m pytest tests -q --tb=no
   ```

   **结果**：**131 passed**，**12 skipped**，约 **26s**（相较纳入 T-032 单测前 +4 条用例）。

### 测试执行（汇总）

| 步骤 | 命令 / 方式 | 结果（本轮） |
|------|-------------|--------------|
| T-032 单测文件 | `pytest tests/unit/test_t032_inventory_migration.py -v` | **4 passed** |
| 全仓库 pytest | `pytest tests -q --tb=no` | **131 passed**，12 skipped |

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 对应规格 / 场景 | 结果 |
|------|---------------|------|-----------------|------|
| TC-001 | `test_t032_tc001_empty_db_creates_section62_schema` | 空库首次打开 → §6.2 表结构 | §6.2 | ✅ 通过 |
| TC-002 | `test_t032_tc002_legacy_name_pk_migrates_to_household_scope` | 旧 `name` 主键表迁移 → 行绑定 SCOPE | §6.2 | ✅ 通过 |
| TC-003 | `test_t032_tc003_legacy_integrity_shape_user_id_mapping` | integrity 旧形映射 | DEV-022 | ✅ 通过 |
| TC-004 | `test_t032_tc004_two_households_isolated_on_same_file` | 双 `household_id` 同库隔离 | §8 | ✅ 通过 |
| TC-005 | 全仓库收集（含本文件及既有用例） | 回归与 NFR-05 | NFR-05 | ✅ 通过 |

### 禁止行为与通用检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `inventory` 访问未使用 `thread_id` 作键 | ✅ | `inventory.py` 仅 `household_id` |
| `task_stack`；业务代码禁用名 `task_queue` | ✅ | `src/**/*.py` 仅 `task_stack.py` 注释提及 |
| `get_all()` 返回 Dict 形态 **I** | ✅ | 键为食材名，值为 `amount`/`unit` |
| AgentState 七切片 / L2 不误改 `recipe_state` | ✅（例行） | 本轮未改 `state.py`/L2；无新风险信号 |

### 观察项（非缺陷、不阻塞 T-032）

- **`DatabaseIntegrityChecker`** 仍使用相对路径字面量 `data/db/inventory.db`，与 `Settings.get_inventory_db_path()` 在「自定义 `paths.db_dir`」时可能不一致；若仅使用默认配置则与 DEV-022「integrity 建表对齐」目标一致。建议后续横切任务（如 T-027）统一路径来源。

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-032**「测试状态」**待测试** → **已完成**。

---

## [TR-028] T-020 功能验证（库存快照 **I** 与 `inventory_state.inventory_snapshot`）

**验证任务**：T-020 / [DEV-023]——`InventoryManager.get_inventory_snapshot_i`（`WHERE household_id = ?` 之上的规范 **I**）；`LogisticsManager.get_inventory_snapshot` 委托；`logistics_manager_node` 文末无条件 `get_inventory_snapshot()` 写入 `updates["inventory_snapshot"]`，经 `runtime_bundle_to_slice_patches` → **`inventory_state.inventory_snapshot`**（§1.2.1 字典型）；`_normalize_inventory_snapshot` 对 dict 逐项 `float`/`str`、兼容 list legacy（**FR-30**；**§6.1**；**§1.2.1**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例**：`tests/unit/test_t020_inventory_snapshot.py`

### 测试过程信息（执行记录）

仓库根目录 `F:\WHAT-TO-EAT-AGENT`：

1. **T-020 专项**

   ```text
   python -m pytest tests/unit/test_t020_inventory_snapshot.py -v --tb=short
   ```

   **结果**：**4 passed**，约 **1.4s**（`test_t020_tc001`～`test_t020_tc004`）。

2. **全量回归**

   ```text
   python -m pytest tests -q --tb=no
   ```

   **结果**：**135 passed**，**12 skipped**，约 **33s**（较 [TR-027] 全量 +4 条用例）。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 依据 | 结果 |
|------|-------------|------|------|------|
| TC-001 | `test_t020_tc001_get_inventory_snapshot_i_shape` | **I** 为 `float`/`str` | §6.1 | ✅ |
| TC-002 | `test_t020_tc002_normalize_inventory_snapshot` | dict / list / 非法根 | §1.2.1 | ✅ |
| TC-003 | `test_t020_tc003_logistics_node_writes_final_i_without_recipe_requirements` | 无 **R** 仍写最终快照至切片 | DEV-023 | ✅ |
| TC-004 | `test_t020_tc004_inv_commit_then_snapshot_reflects_deduction` | 扣减后快照与 DB 一致 | FR-30 | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| 库存 SQL 键为 `household_id`，非 `thread_id` | ✅（与 T-032 / `inventory.py` 一致） |
| `task_queue` 禁用名 | ✅（例行） |
| `inventory_snapshot` 为 Dict 形态 **I** | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-020**「测试状态」**待测试** → **已完成**。

---

## [TR-029] T-033 功能验证（§6.5 补货预览 / 确认 / `apply_restock`）

**验证任务**：T-033 / [DEV-024]——`_build_add_preview_from_restock_rows`；`TASK_INV_ADD` 与 `slots.restock_items` / `restock_confirm`；`Settings.get_inventory_restock_confirm_required`；`InventoryManager.apply_restock`；`_restock_pending_confirm_shortcut`（**规格 §6.5**；**§9**）。

**验证时间**：2026-05-07

**最终结论**：❌ 有缺陷（业务路径与单测多数通过；**§9 `error_state` 未随节点返回**，见 BUG-002）

**测试文档与用例**：`tests/unit/test_t033_restock_preview.py`

### 测试过程信息（执行记录）

```text
python -m pytest tests/unit/test_t033_restock_preview.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果（本轮）**：T-033 文件 **8 passed**；全量 **143 passed**，**12 skipped**，约 **30s**。

**回归维护**：T-021 §6.3 扣减守卫上线后，`TASK_INV_COMMIT` 单测需会话 **`recipe_use_confirmed=True`**。已同步 **`tests/unit/t001-031Intent/test_logistics_silent_gap.py`**（`test_silent_precalc_runs_after_inv_commit`）与 **`tests/unit/test_t020_inventory_snapshot.py`**（`test_t020_tc004_*`），与扣减前置条件一致。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 结果 |
|------|-------------|------|------|
| TC-001 | `test_t033_tc001_build_preview_valid_row` | 预览解析与 `merge_mode` | ✅ |
| TC-002 | `test_t033_tc002_unparsed_only_inventory_add_unparsed` | `add_status=failed` + `error_code=INVENTORY_ADD_UNPARSED` | ✅（BUG-002 关闭后补齐断言） |
| TC-003 | `test_t033_tc003_partial_unresolved_pending` | 部分 unresolved → pending | ✅ |
| TC-004 | `test_t033_tc004_confirm_required_pending_no_write` | 需确认时不写库 | ✅ |
| TC-005 | `test_t033_tc005_auto_commit_single_when_confirm_off` | 单条自动写库 | ✅ |
| TC-006 | `test_t033_tc006_two_step_confirm_writes` | 确认后轮写入 | ✅ |
| TC-007 | `test_t033_tc007_apply_restock_add_vs_set` | `apply_restock` add/set | ✅ |
| TC-008 | `test_t033_tc008_router_pending_confirm_shortcut` | 路由短句确认 | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| 库存键非 `thread_id` | ✅ |
| `task_stack` / 禁用 `task_queue` | ✅（例行） |

### 缺陷列表（初审）

- **BUG-002**：见下文 **[BUG-002]**；已于 **[TR-031]** 复审关闭。

### 开发计划同步（初审）

已将 `docs/开发计划.md` §3：**T-033**「测试状态」标为 **待修改**（关联 BUG-002）。复审收口见 **[TR-031]**。

---

## [BUG-002] logistics 节点设置的 `error_state` 未写入返回补丁（§9 错误码丢失）

**严重程度**：`P2-一般`

**所属任务**：T-033（波及 T-022 失败话术与 §9 对齐）

**违反规格**：规格 §9；DEV-024 中「`INVENTORY_ADD_UNPARSED` / `INVENTORY_WRITE_FAILED`」

**发现时间**：2026-05-07

**状态**：`已关闭`（复审见 **[TR-031]**；修复 **[DEV-026]** / **[TR-030]**）

### 问题描述

`logistics_manager_node` 在 `TASK_INV_ADD` 等分支中向 `updates` 写入 **`error_code`**（如 `INVENTORY_ADD_UNPARSED`）。合并后的 `new_logistics_buffer` 含 `error_state` 键，但 **`runtime_bundle_to_slice_patches(lb)` 仅产出 `recipe_state` / `inventory_state` / `control_state`（及可选 `memory_state`）**，未将 `lb["error_state"]` 映射到返回字典，导致节点 **`return out` 不包含 `error_state`**，校验 §9 枚举的用户可见失败路径不完整。

### 复现步骤

1. 构造 `task_stack` 含 `TASK_INV_ADD`，`slots.restock_items=[{"name":"鸡蛋"}]`（无 amount）。  
2. 调用 `logistics_manager_node`。  
3. 观察返回值：可无 **`error_state.error_code`**；inventory 侧可有 **`add_status=="failed"`**。

### 预期行为

返回值应包含 **`error_state`**，且 **`error_code == INVENTORY_ADD_UNPARSED`**（与规格 §9、DEV-024 一致）。

### 实际行为（修复前）

`out.get("error_state")` 常为缺省空结构或未携带上述 `error_code`；业务仍可能通过 `add_status` 区分失败，但 **错误码未随状态图传播**。（**修复后**：见 **[TR-031]** 复审，`runtime_bundle_to_slice_patches` 转发 `error_state`。）

### 根因分析（测试侧初步判断）

`src/agent/state_sync.py` 中 `runtime_bundle_to_slice_patches` 未处理展平 `lb` 的 **`error_state`** 字段；`logistics` 未在 `return` 前单独合并 `error_state` 补丁。

### 影响范围

- 影响场景：补货解析失败、写库部分失败等需 §9 码的交互与 T-022 显式反馈。  
- 影响任务：T-033 初审「有缺陷」直至 BUG 修复；复审收口见 **[TR-031]**。

**备注**：开发合入见 **[TR-030]** / [DEV-026]；测试 Agent 已于 **[TR-031]** 关闭 BUG 并将 **`docs/开发计划.md` §3 T-033** 标为 **已完成**。

---

## [TR-030] BUG-002 开发修复记录（§9 `error_state` 随 `runtime_bundle_to_slice_patches` 传播）

**关联缺陷**：BUG-002 · **关联开发日志**：`docs/dev_log.md` [DEV-026]

**记录时间**：2026-05-07

**修复结论（开发侧）**：✅ 已合入实现；**测试复审**：见 **[TR-031]**（BUG-002 已关闭，T-033 已完成）。

### 根因（与 BUG-002 一致）

`logistics_manager_node` 合并后的展平 `lb` 含 **`error_state`**，但 **`runtime_bundle_to_slice_patches(lb)`** 未生成 **`error_state`** 切片补丁，节点 **`return`** 未携带 §9 字段，LangGraph **`merge_slice`** 无法更新 **`AgentState.error_state`**。

### 修复要点

| 项 | 说明 |
|----|------|
| `runtime_bundle_to_slice_patches` | 若 **`"error_state" in lb`**，则 **`patches["error_state"]`** 写入（与 **`CLEAR_ERROR_STATE`** 清场合规一致）。 |
| `materialize_runtime_bundle_from_slices` | 将 **`state["error_state"]`** 并入展平 **`flat["error_state"]`**，保证 **`get_runtime_bundle`** 与切片往返一致。 |
| 变更文件 | `src/agent/state_sync.py` |

### 开发侧自测（非最终验收）

```text
python -m pytest tests/unit/test_t033_restock_preview.py -v --tb=short
```

**结果**：`8 passed`（与 DEV-026 一致）。全量回归以测试 Agent 命令与结论为准。

### 说明

- **不在本条修改** `docs/开发计划.md` 中任何任务的「测试状态」列（避免开发与测试角色混写）。  
- BUG 关闭与 T-033 收口：见 **[TR-031]**（测试 Agent 复审）。

---

## [TR-031] BUG-002 复审与 T-033 收口

**关联**：BUG-002 · `docs/dev_log.md` **[DEV-026]** · 初审 **[TR-029]** · 开发记录 **[TR-030]**

**复审时间**：2026-05-07

### 【复审结论 BUG-002】

**复现步骤验证**：按 [BUG-002] 原步骤（`TASK_INV_ADD` + `restock_items=[{"name":"鸡蛋"}]`，无 amount）调用 `logistics_manager_node`；返回值 **`out["error_state"]["error_code"] == INVENTORY_ADD_UNPARSED`** ✅（单测 `test_t033_tc002_unparsed_only_inventory_add_unparsed` 已断言）。

**回归检查**：`python -m pytest tests -q --tb=no` → **143 passed**，**12 skipped**，约 **29s** ✅；未发现新失败。

**结论**：**BUG-002 关闭** ✅

### T-033 最终结论（复审后）

**§6.5 补货预览 / 确认 / §9 错误码传播**：与规格及 [DEV-024]、[DEV-026] 对齐；**T-033 功能验证通过**，可标「已完成」。

### 测试过程信息（复审轮）

```text
python -m pytest tests/unit/test_t033_restock_preview.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果**：T-033 文件 **8 passed**（含 TC-002 对 `error_state` 的硬性断言）；全量 **143 passed**，12 skipped。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-033**「测试状态」**待修改** → **已完成**。

---

## [TR-032] T-021 功能验证（§6.3 `TASK_INV_COMMIT` / FR-31）

**验证任务**：T-021 / [DEV-025]——`logistics_manager_node` 在 **`TASK_INV_COMMIT`** 下：`recipe_use_confirmed` 或当轮 **`recipe_adopt`** / **`recipe_adoption`** 槽位才允许 **`batch_deduct`**；否则 **`commit_status=blocked_no_confirm`**；菜名锚点与锁定菜不一致 → **`blocked_recipe_mismatch`** + **`COMMIT_RECIPE_MISMATCH`**；成功扣减后 **`recipe_use_confirmed=False`**；**R** 空 → **`skipped`**（**规格 §6.3**；**FR-31**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例**：`tests/unit/test_t021_inv_commit_section63.py`

### 测试过程信息

```text
python -m pytest tests/unit/test_t021_inv_commit_section63.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果**：T-021 专项 **5 passed**（约 **3.4s**）；全量 **148 passed**，**12 skipped**，约 **33s**。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 结果 |
|------|--------------|------|------|
| TC-001 | `test_t021_tc001_skipped_when_no_recipe_requirements` | **R** 空 → `skipped` | ✅ |
| TC-002 | `test_t021_tc002_blocked_no_confirm_no_deduct` | 未确认 → `blocked_no_confirm`、库存不变 | ✅ |
| TC-003 | `test_t021_tc003_success_clears_recipe_use_confirmed` | 已确认 → 扣减成功并清除标记 | ✅ |
| TC-004 | `test_t021_tc004_recipe_adopt_this_turn_allows_commit` | 当轮 `recipe_adopt` → 允许扣减 | ✅ |
| TC-005 | `test_t021_tc005_blocked_recipe_mismatch_error_code` | 菜名不一致 → `COMMIT_RECIPE_MISMATCH` | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| `task_queue` 禁用名（例行） | ✅ |
| §9：`error_state` 随节点返回（TC-005） | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-021**「测试状态」**待测试** → **已完成**。

---

## [TR-034] T-022 功能验证（库存写失败显式反馈 / FR-32）

**验证任务**：T-022 / [DEV-027]——`InventoryManager.batch_deduct_report`；`LogisticsManager.update_inventory_after_cooking_report`；`TASK_INV_COMMIT` 在 **`partial_success` / `failed`** 时写入 **`commit_succeeded_items` / `commit_failed_items`** 与 **`error_state.error_code=INVENTORY_WRITE_FAILED`**；仅 **`success`** 清除 **`recipe_use_confirmed`**；**`TASK_INV_ADD`** 确认路径的 **`add_succeeded_items` / `add_failed_items`**；**`GeneratorNode.handle_inv_commit` / `handle_inv_add`** 对齐 FR-32，禁止用笼统「已全部成功」掩盖部分失败（**FR-32**；**§6.4**；**§6.5.5**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例**：`tests/unit/test_t022_inventory_write_feedback.py`

### 测试过程信息

```text
python -m pytest tests/unit/test_t022_inventory_write_feedback.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果（本轮）**：T-022 专项 **5 passed**（约 **6s**）；全量 **`pytest tests`**：**153 passed**，**12 skipped**，约 **32s**。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 结果 |
|------|--------------|------|------|
| TC-001 | `test_t022_tc001_batch_deduct_report_partial` | `batch_deduct_report` 部分失败 | ✅ |
| TC-002 | `test_t022_tc002_logistics_commit_partial_lists_and_error_state` | 扣减 partial → 名单 + §9；不清理 `recipe_use_confirmed` | ✅ |
| TC-003 | `test_t022_tc003_logistics_commit_failed_all` | 扣减全失败 | ✅ |
| TC-004 | `test_t022_tc004_generator_commit_and_add_no_false_success_wording` | generator 话术 | ✅ |
| TC-005 | `test_t022_tc005_logistics_add_confirm_partial_success_lists` | 补货 partial 名单 | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| `error_state` 随节点补丁（TC-002/003/005） | ✅ |
| `task_queue` 例行 | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

**T-022**「测试状态」在 **`docs/开发计划.md` §3** 应为 **已完成**（与 [DEV-027] 一致）；若仍为「待测试」请保存后刷新。

### 编号说明

本文档中 **[TR-022]** 已用于 **T-016**（历史命名），故 **T-022 任务** 的验证记录使用 **[TR-034]**，避免与既有 TR 编号混淆。

---

## [TR-035] T-023 功能验证（购物缺口缓存与显式交付 / FR-40～42）

**验证任务**：T-023 / [DEV-028]——**`_gap_cache_valid`**（`gap_basis` 与当前 **R**/**I** 指纹一致且 `cached_shopping_gap` 可用）；**`_apply_silent_gap_precalc`** 命中时跳过 **`calculate_shopping_gap`**、**`gap_delivery_mode=cache`**；未命中则 **§7.2** 全量重算、**`gap_delivery_mode=fresh`**；**`TASK_GAP_CALC`** 且无 **R** → **`GAP_CACHE_MISS`**、**`gap_delivery_mode=empty`**；**`GeneratorNode.handle_gap_calc`** 缓存与缺 **R** 话术；**`_merge_shopping_gap_overlay`** 最小 overlay（**FR-40～FR-42**；**§7.1～§7.3**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例**：`tests/unit/test_t023_gap_cache.py`

### 测试过程信息

```text
python -m pytest tests/unit/test_t023_gap_cache.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果（本轮）**：T-023 专项 **6 passed**（约 **7s**）；全量 **159 passed**，**12 skipped**，约 **40s**。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 结果 |
|------|--------------|------|------|
| — | `test_t023_gap_cache_valid_requires_matching_fingerprints` | `_gap_cache_valid` 正/反例 | ✅ |
| — | `test_t023_silent_precalc_skips_recalc_when_cache_hits` | 静默路径缓存命中、不调用 `calculate_shopping_gap` | ✅ |
| — | `test_t023_silent_precalc_fresh_when_basis_stale` | 指纹失效 → fresh | ✅ |
| — | `test_t023_task_gap_calc_no_r_gap_cache_miss` | 无 **R** + `TASK_GAP_CALC` → §9 | ✅ |
| — | `test_t023_generator_gap_cache_and_miss` | `handle_gap_calc` 话术 | ✅ |
| — | `test_t023_merge_overlay_remove` | overlay `remove` | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| `task_stack` / 禁用 `task_queue`（例行） | ✅ |
| §9：`GAP_CACHE_MISS` 随节点返回 | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-023**「测试状态」**待测试** → **已完成**。

---

## [TR-036] T-024 功能验证（购物清单 overlay 与 `list_action` / FR-41、FR-43）

**验证任务**：T-024 / [DEV-029]——**`_merge_shopping_gap_overlay`**（**`pending_manual`** + **`shopping_list`** 底表，顺序 overlay **`remove` / `adjust_note` / `add`**）；**`_apply_list_action_to_overlay_updates`**（**`refresh_gap`** 清空 **`shopping_list_overlay`** 并失效 **`gap_basis`**；**`mark_bought`** + **`mark_bought_items`** → **`remove`**；**`edit_overlay`** + **`list_edit_ops`**）；**`_coerce_list_edit_ops`**；静默路径下 **`mark_bought`** 与缓存交付叠加；**`GeneratorNode.handle_gap_calc`** overlay 非空时的手动调整提示（**§7.4**；**§11.2**）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**测试文档与用例**：`tests/unit/test_t024_shopping_list_overlay.py`

### 测试过程信息

```text
python -m pytest tests/unit/test_t024_shopping_list_overlay.py -v --tb=short
python -m pytest tests -q --tb=no
```

**结果（本轮）**：T-024 专项 **8 passed**（约 **8s**）；全量 **167 passed**，**12 skipped**，约 **36s**。

### 测试用例执行情况

| 用例 | pytest 节点 | 描述 | 结果 |
|------|--------------|------|------|
| — | `test_t024_merge_base_order_pending_manual_then_shopping_list` | 底表顺序 | ✅ |
| — | `test_t024_merge_overlay_adjust_note_then_add` | overlay 备注与 `add` | ✅ |
| — | `test_t024_apply_refresh_gap_clears_overlay_and_invalidates_basis` | `refresh_gap` | ✅ |
| — | `test_t024_apply_mark_bought_appends_remove` | `mark_bought` | ✅ |
| — | `test_t024_apply_edit_overlay_list_edit_ops` | `edit_overlay` | ✅ |
| — | `test_t024_coerce_list_edit_ops_add_display_alias` | `_coerce_list_edit_ops` | ✅ |
| — | `test_t024_logistics_mark_bought_merges_remove_into_display` | logistics 端到端 | ✅ |
| — | `test_t024_generator_overlay_manual_adjust_hint` | `handle_gap_calc` | ✅ |

### 禁止行为与通用检查

| 检查项 | 结果 |
|--------|------|
| `task_stack` / 禁用 `task_queue`（例行） | ✅ |

### 缺陷列表

- 本轮未登记新 BUG。

### 开发计划同步

已将 `docs/开发计划.md` §3：**T-024**「测试状态」**待测试** → **已完成**。

---

## [TR-037] INT-M4 库存与清单模块集成验收（M4 / §6～§7）

**验证任务**：在 **T-020、T-021、T-022、T-023、T-024、T-032、T-033** 等单测之上，对 **M4 库存与清单**做跨任务串联与话术冒烟：**TASK_INV_COMMIT** → **TASK_INV_CHECK** 与真实 DB 一致；**TASK_INV_CHECK** + **TASK_GAP_CALC** 同轮触发静默缺口 **fresh**；`materialize_runtime_bundle_from_slices` / `get_runtime_bundle` 保留 **overlay** 与展示行备注；**Generator** `handle_inv_check` / `handle_gap_calc` / `handle_inv_commit`；参数化断言任一分支后 **`inventory_snapshot`** 为 **dict**（§1.2.1）。

**验证时间**：2026-05-07

**最终结论**：✅ 通过

**集成用例文件**：`tests/integration/test_m4_inventory_list_module.py`

### 测试过程信息

```text
python -m pytest tests/integration/test_m4_inventory_list_module.py -v --tb=short
python -m pytest tests/unit/test_t020_inventory_snapshot.py tests/unit/test_t021_inv_commit_section63.py tests/unit/test_t022_inventory_write_feedback.py tests/unit/test_t023_gap_cache.py tests/unit/test_t024_shopping_list_overlay.py tests/unit/test_t032_inventory_migration.py tests/unit/test_t033_restock_preview.py tests/integration/test_m4_inventory_list_module.py tests/unit/t001-031Intent/test_logistics_silent_gap.py -q --tb=no
python -m pytest tests -q --tb=no
```

**结果（本轮）**：INT-M4 专项 **8 passed**（约 **9s**）；M4 相关单测 + 集成子集（上列 9 个文件）**52 passed**（约 **21s**）；全量 **175 passed**，**12 skipped**，约 **35s**。

### 集成用例执行情况

| 用例 | 描述 | 结果 |
|------|------|------|
| `test_m4_db_chain_commit_then_inv_check_snapshot_matches_db` | 扣减后再次查库存与 DB 一致 | ✅ |
| `test_m4_combined_inv_check_and_gap_calc_triggers_silent_recalc` | 查库存 + 显式清单同轮、**fresh** | ✅ |
| `test_m4_slice_roundtrip_overlay_preserved_in_bundle` | 切片往返与 overlay 备注 | ✅ |
| `test_m4_generator_inventory_gap_and_commit_handles_smoke` | 生成器库存/缺口/扣减话术 | ✅ |
| `test_m4_inventory_snapshot_always_dict_after_node` | 多 `task_stack` 形态下 **I** 为 dict | ✅ |

### 关联单测清单（本模块完整回归推荐）

| 任务 | 文件 |
|------|------|
| T-020 | `tests/unit/test_t020_inventory_snapshot.py` |
| T-021 | `tests/unit/test_t021_inv_commit_section63.py` |
| T-022 | `tests/unit/test_t022_inventory_write_feedback.py` |
| T-023 | `tests/unit/test_t023_gap_cache.py` |
| T-024 | `tests/unit/test_t024_shopping_list_overlay.py` |
| T-032 | `tests/unit/test_t032_inventory_migration.py` |
| T-033 | `tests/unit/test_t033_restock_preview.py` |
| T-002 静默缺口 | `tests/unit/t001-031Intent/test_logistics_silent_gap.py` |

### 缺陷列表

- 本轮未登记新 BUG。

---

## 缺陷汇总

| BUG 编号 | 严重程度 | 所属任务 | 描述 | 状态 | 关闭日期 |
|---------|---------|---------|------|------|---------|
| BUG-001 | P2 | T-030 / T-002 | 静默缺口单测断言 `logistics_buffer`，与切片返回不一致 | ✅ 已关闭 | 2026-05-06 |
| BUG-002 | P2 | T-033 | `error_state` 未随 logistics 返回补丁，§9 码丢失 | ✅ 已关闭 | 2026-05-07 |

<!-- 测试 Agent 在此追加缺陷记录 -->
