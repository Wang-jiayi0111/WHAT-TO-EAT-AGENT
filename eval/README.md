# E2E 测评使用说明

面向开发者：如何用本仓库的 **`eval/`** 包对 Agent 做**端到端采集 + 分层打分**，并得到易读报告。

---

## 1. 两条命令在做什么

| 步骤 | 命令 | 产出 |
|------|------|------|
| **① 采集** | `python -m eval.run_e2e` | `docs/evals/runs/<run_id>/captures/*.json`、`manifest.json` |
| **② 打分** | `python -m eval.score_run`（或 `--run-id <run_id>`） | 同目录下 `scores.json`、`scores_report.md`；**T-043** 另写单用例 `docs/evals/cases/<run_id>/*.md`、`e2e_summary.md`，并更新 `manifest.json` |

先跑 **①**，记下终端里的 **`run_id`**（或看 `docs/evals/runs/` 下最新目录名），再跑 **②**。

### `golden_recipe_ids` 与检索指标（§5.1）

写在每条用例 **`fixture.expected.golden_recipe_ids`**，用于 **T-042** 检索层（详见 **`scores.json`** → `cases[].layers.retrieval.submetrics`）：

| 子指标 | 含义 |
|--------|------|
| **`retrieval_recall`** / **`recall_hit_at_k`** | **召回**：候选列表中是否命中**至少一条**金标（多条金标为 **OR**）。 |
| **`retrieval_accuracy_top1`** | **准确率（Hit@1）**：排序**第一条**候选（标题优先，无标题则用首条 id）是否与**任一**金标语干匹配。 |
| **`golden_rank`** | **名次**：最佳命中位次的 **`1/rank`**（越靠前越高）。 |

检索层加权：**0.4×召回 + 0.3×Top1准确率 + 0.3×名次分**。未命中任一金标时仍可触发检索硬失败封顶（可用 `--no-retrieval-hard-fail` 关闭）。

### `expected.intents`（对话层多意图，T-042）

可选 **`fixture.expected.intents`**：字符串列表，与末轮快照 **`intents`** 做**子集召回**（顺序无关；实际可多意图）。与 **`primary_intent`** 同时声明时，对话层 **`intent_match`** 为二者得分算术平均；详见 `eval/scoring.py` → `compute_intent_alignment_score`。

### `e2e_seed` 与清单断言 `shopping_list_assert`

- **`e2e_seed`**（可选）：写在**用例对象顶层**（与 `case_id` 同级）。仅在**该用例第一轮** `ainvoke` 前合并进状态（`recipe_state`、`inventory_state` 等切片）。用于注入 **`recipe_requirements` + `inventory_snapshot` + `cached_shopping_gap`**，使「索要清单 / 勾掉一项 / mark_bought」等有确定上下文。
- **`expected.shopping_list_assert`**（可选）：对**末轮**快照中的 **`inventory_state`** 做结构化校验（见 `eval/scoring.py` → `score_shopping_list_ops_layer`）。常用键：
  - **`overlay_remove_keys_contain`**：`shopping_list_overlay` 中 `remove` 操作是否覆盖所列食材名（模糊包含）。
  - **`gap_shopping_names_contain`** / **`gap_missing_names_contain`**：缺口清单是否出现所列食材。
  - **`gap_cache_present`**：是否要求存在 `cached_shopping_gap`（布尔）。
  - **`overlay_ops_min`**：overlay 条数下限。
  - **`strict`**：为 `true` 且任一子项失败时，触发与检索封顶类似的 **overall 封顶**。

配置了 **`shopping_list_assert`** 且可打分时，总分采用 **四档权重**：检索 0.28 · 生成 0.27 · 对话 0.25 · **清单操作 0.20**。

---

## 2. 推荐顺序（复制即用）

在项目根目录执行：

```bash
# 1）跑全部用例（eval/cases 下各 *.json 中的数组项），落盘采集
python -m eval.run_e2e

# 只跑一个用例文件（仅写文件名即可，须在项目根执行）
python -m eval.run_e2e --cases-dir shopping_list.json

# 2）打分（默认对 docs/evals/runs/ 下「最新」一次 run；亦可显式指定）
python -m eval.score_run
# python -m eval.score_run --run-id eval_20260208_153045_a1b2c3d4
```

打开易读报告：

- **`docs/evals/runs/<run_id>/scores_report.md`**（分项表）
- **`docs/evals/runs/<run_id>/e2e_summary.md`** 或项目根 **`docs/agent_eval_report.md`**（测评总报告，NFR-11）
- 单用例（§5.5 链路树 + 分项）：**`docs/evals/cases/<run_id>/<case_id>.md`**

机器可读全量：

- **`docs/evals/runs/<run_id>/scores.json`**

仅基于已有分数重生成 T-043 产出：

```bash
python -m eval.e2e_reports --run-id <run_id>
```

---

## 3. 常用参数

### `run_e2e`

| 参数 | 说明 |
|------|------|
| `--cases-dir DIR_OR_JSON` | 用例**目录**（默认 `eval/cases`）；或**单个** `.json` 的相对/绝对路径；或**仅文件名**如 `shopping_list.json`（自动解析为 `<项目根>/eval/cases/shopping_list.json`） |
| `--run-id <字符串>` | 固定本次 run 目录名（可选） |
| `--case-filter <子串>` | 只跑 `case_id` 包含该子串的用例 |
| `--fail-fast` | 第一条失败则停止后续用例 |
| `--user-id <id>` | 传入 Agent 的 `active_user_id`，默认 `default_user` |

### `score_run`

| 参数 | 说明 |
|------|------|
| （省略 `--run-dir` / `--run-id`） | **默认**选用 `docs/evals/runs/` 下含 `captures/` 的目录中 **mtime 最新** 的一次 |
| `--run-id <id>` | 指定 run 目录名（与默认最新二选一） |
| `--run-dir <路径>` | 直接指定含 `captures/` 的目录 |
| `--no-llm` | 不调评测 LLM；生成层用启发式幻觉，对话层用规则澄清 |
| `--no-retrieval-hard-fail` | 关闭「有金标但检索零命中」时的总分封顶 |
| `--latest` | 额外写 `docs/evals/latest_eval.json`（仅汇总数字） |
| `--no-report-md` | 只写 `scores.json`，不生成 `scores_report.md` |
| `--no-t043` | 跳过单用例 MD、总报告与 manifest 的 `t043` 增补 |
| `--no-agent-eval-main` | T-043 仍写 run 内与 `e2e_summary_<run_id>.md`，但不覆盖 `docs/agent_eval_report.md` |

---

## 4. 与 `src.observability.eval` 的区别（避免混淆）

| 命令 | 典型产物 | 用途 |
|------|----------|------|
| `python -m eval.run_e2e` + `eval.score_run` | `runs/<id>/scores_report.md` | **固定用例集**跑 Agent → **自动算分**（规则 + 可选 LLM） |
| `python -m src.observability.eval` | （若有）规格向壳脚本 | **E2E 定稿总览**以 `eval.score_run` → **`docs/agent_eval_report.md`**（T-043）为准 |

两者都是对 Agent 的评估，但**入口与成绩单位置不同**；日常「跑完 cases 看分数」走 **`eval`** 这条线即可。

---

## 5. 代码入口（便于跳转）

- 采集 CLI：`eval/run_e2e.py` → `eval/runner.py`（`run_suite`、`build_e2e_snapshot`）
- 快照组装：`eval/state_capture.py`
- 打分 CLI：`eval/score_run.py` → `eval/scoring.py`、`eval/scoring_llm.py`
- T-043 报告：`eval/e2e_reports.py`（`python -m eval.e2e_reports`）
- LLM 评委 Prompt：`src/agent/prompts/eval_judge_quality.md`

---

## 6. 前置条件

- `config/setting.yaml` 等能通过 `run_startup_configuration_check`（与主程序一致）。
- 打分若启用默认 **LLM 评委**：需配置可用的 LLM（与 `LLMFactory` / Settings 一致）；离线或只想规则分时使用 **`--no-llm`**。
