# Eval Cases 用例集审核报告

- **首次生成**：2026-05-09  
- **重新评估**：2026-05-09（本轮已对照磁盘上 `eval/cases/*.json` 全量复核；脚本校验规则 1–5 **0 失败**）  
- **范围**：`eval/cases/*.json`  
- **用例总数**：72  

---

## 1. 审核项说明

| 序号 | 检查项 | 规则 |
|------|--------|------|
| 1 | `case_id` 格式 | 符合 `{category}_{三位数}`（前缀可含下划线，后缀为三位数字） |
| 2 | 检索类 `golden_recipe_ids` | **检索类** = `primary_intent === "recipe_search"` 时，`golden_recipe_ids` 不得为空数组 |
| 3 | 忌口类 `output_excludes` | **忌口类** = `scenario_category === "dietary_filter"` 时，`output_excludes` 不得为空数组 |
| 4 | `multi_turn` 轮数 | `scenario_category === "multi_turn"` 时，`user_turns` 至少 2 轮 |
| 5 | 澄清字段一致性 | `needs_clarification` 与 `clarification_triggered` 同真或同假 |
| 6 | `eval_method` | 与断言强度、任务类型是否匹配（`auto` / `llm_judge` / `human`） |

---

## 2. 汇总（本轮）

| 结果 | 数量 | 说明 |
|------|------|------|
| **pass** | 67 | 规则 1–6 均无告警项 |
| **warn** | 5 | 规则 1–5 已通过脚本校验；规则 6 或 golden 语义约定上建议优化 |
| **fail** | 0 | 规则 1–5 无违反 |

---

## 3. 失败项（fail）

**当前无。** 此前 `nutrition_query_005` 曾因检索类金标为空列为 fail；现已填入 `golden_recipe_ids`：`["recipe_id_菠菜炒鸡蛋"]`（见 `recipe_search.json`）。

---

## 4. 警告项（warn）

| case_id | 文件 | 原因 |
|---------|------|------|
| `recipe_query_046` | `help.json` | `primary_intent` 为 `help`，`scenario_category` 为 `recipe_query`，且含非空 `golden_recipe_ids`（`recipe_id_西红柿炒鸡蛋`）。与「帮助说明」语义并存时需约定：流水线是否仍用 golden 做菜谱对齐、是否仅作文档示例。 |
| `recipe_query_052` | `out_of_scope.json` | 违规/安全拒答场景下仍填写 `golden_recipe_ids`（`recipe_id_凉拌黄瓜`）。`eval_method` 为 `human`，但若自动化阶段误读 golden，可能与安全期望冲突，需在评测文档中写明是否忽略 golden。 |
| `multi_turn_059` | `recipe_adopt.json` | 跨轮采纳「第二道葱油拌面」，`golden_recipe_ids` 为空；若需与会话候选菜谱 ID 严格对齐，建议补金标。 |
| `edge_case_038` | `general_chat.json` | `output_contains`、`output_excludes` 均为空，`eval_method` 为 `llm_judge`，主观波动大，缺少关键词锚点。 |
| `ambiguity_068` | `user_clarify.json` | `eval_method` 为 `auto`，且输出断言为空，自动化难以约束「选 3」后的行为（除非 harness 单独解析结构化状态）。 |

---

## 5. 本轮相对上一版报告的变更摘要

| 区域 | 变更要点 |
|------|----------|
| `recipe_search.json` | **`nutrition_query_005`** 已补充非空 `golden_recipe_ids`（`recipe_id_菠菜炒鸡蛋`），硬性规则 2 通过 |

---

## 6. 按文件一览（每条用例结论）

| 文件 | case_id | 结论 |
|------|---------|------|
| `dietary_advice.json` | nutrition_query_019 ~ edge_case_024（6 条） | pass |
| `general_chat.json` | edge_case_037 | pass |
| | edge_case_038 | warn |
| | nutrition_query_039 ~ ambiguity_042 | pass |
| `help.json` | edge_case_043 ~ edge_case_044 | pass |
| | inventory_045 | pass |
| | recipe_query_046 | warn |
| | multi_turn_047 ~ edge_case_048 | pass |
| `inventory_add.json` | inventory_013 ~ edge_case_018（6 条） | pass |
| `inventory_check.json` | inventory_007 ~ edge_case_012（6 条） | pass |
| `inventory_commit.json` | inventory_031 ~ edge_case_036（6 条） | pass |
| `out_of_scope.json` | edge_case_049 ~ edge_case_051 | pass |
| | recipe_query_052 | warn |
| | multi_turn_053 ~ edge_case_054 | pass |
| `profile_sync.json` | multi_turn_061 ~ edge_case_066（6 条） | pass |
| `recipe_adopt.json` | recipe_query_055 ~ dietary_filter_058 | pass |
| | multi_turn_059 | warn |
| | edge_case_060 | pass |
| `recipe_search.json` | recipe_query_001 ~ multi_turn_006（6 条） | pass |
| `shopping_list.json` | shopping_list_025 ~ edge_case_030（6 条） | pass |
| `user_clarify.json` | ambiguity_067 | pass |
| | ambiguity_068 | warn |
| | multi_turn_069 ~ edge_case_072 | pass |

---

## 7. 全局检查摘要（规则 1 / 3 / 4 / 5）

- **规则 1**：脚本校验 72 条 `case_id` 均匹配 `.+_\d{3}`。  
- **规则 2**：全部 `primary_intent === "recipe_search"` 的用例 `golden_recipe_ids` 非空。  
- **规则 3**：三条 `dietary_filter_*`（`recipe_search.json` 中 `dietary_filter_002`，`recipe_adopt.json` 中 `dietary_filter_058`，`profile_sync.json` 中 `dietary_filter_063`）的 `output_excludes` 均非空。  
- **规则 4**：所有 `scenario_category === "multi_turn"` 的用例，`user_turns` 均 ≥ 2。  
- **规则 5**：未发现 `needs_clarification` 与 `clarification_triggered` 不一致。  

---

## 8. 后续建议

1. 在评测 README 或 harness 中明确：`help` + `recipe_query` 场景、`out_of_scope` + `golden` 场景下 golden 的读取策略。  
2. 对 **ambiguity_068** 考虑增加结构化期望（或改为 `llm_judge`）。  
3. 可选：为 **multi_turn_059** 补金标以便自动对齐候选菜谱 ID；**edge_case_038** 增加轻量关键词或改为 `human`。  

---

*本报告由固定口径脚本复核（规则 1–5）与人工摘要整理；修改 JSON 后请更新日期并重新运行校验。*
