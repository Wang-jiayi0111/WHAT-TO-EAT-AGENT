# E2E 测评使用说明

面向开发者：如何用本仓库的 **`eval/`** 包对 Agent 做**端到端采集 + 分层打分**，并得到易读报告。

---

## 1. 两条命令在做什么

| 步骤 | 命令 | 产出 |
|------|------|------|
| **① 采集** | `python -m eval.run_e2e` | `docs/evals/runs/<run_id>/captures/*.json`、`manifest.json` |
| **② 打分** | `python -m eval.score_run --run-id <run_id>` | 同目录下 `scores.json`（全量）、`scores_report.md`（易读表） |

先跑 **①**，记下终端里的 **`run_id`**（或看 `docs/evals/runs/` 下最新目录名），再跑 **②**。

---

## 2. 推荐顺序（复制即用）

在项目根目录执行：

```bash
# 1）跑全部用例（eval/cases 下各 *.json 中的数组项），落盘采集
python -m eval.run_e2e

# 2）把上一步打印的 run_id 替换到下面（示例）
python -m eval.score_run --run-id eval_20260208_153045_a1b2c3d4
```

打开易读报告：

- **`docs/evals/runs/<run_id>/scores_report.md`**

机器可读全量：

- **`docs/evals/runs/<run_id>/scores.json`**

---

## 3. 常用参数

### `run_e2e`

| 参数 | 说明 |
|------|------|
| `--cases-dir <路径>` | 用例目录，默认 `eval/cases` |
| `--run-id <字符串>` | 固定本次 run 目录名（可选） |
| `--case-filter <子串>` | 只跑 `case_id` 包含该子串的用例 |
| `--fail-fast` | 第一条失败则停止后续用例 |
| `--user-id <id>` | 传入 Agent 的 `active_user_id`，默认 `default_user` |

### `score_run`

| 参数 | 说明 |
|------|------|
| `--run-dir <路径>` | 直接指定含 `captures/` 的目录（与 `--run-id` 二选一） |
| `--no-llm` | 不调评测 LLM；生成层用启发式幻觉，对话层用规则澄清 |
| `--no-retrieval-hard-fail` | 关闭「有金标但检索零命中」时的总分封顶 |
| `--latest` | 额外写 `docs/evals/latest_eval.json`（仅汇总数字） |
| `--no-report-md` | 只写 `scores.json`，不生成 `scores_report.md` |

---

## 4. 与 `src.observability.eval` 的区别（避免混淆）

| 命令 | 典型产物 | 用途 |
|------|----------|------|
| `python -m eval.run_e2e` + `eval.score_run` | `runs/<id>/scores_report.md` | **固定用例集**跑 Agent → **自动算分**（规则 + 可选 LLM） |
| `python -m src.observability.eval` | `docs/agent_eval_report.md` | 规格向**评估报告壳**（量表、附录等），数据源不同 |

两者都是对 Agent 的评估，但**入口与成绩单位置不同**；日常「跑完 cases 看分数」走 **`eval`** 这条线即可。

---

## 5. 代码入口（便于跳转）

- 采集 CLI：`eval/run_e2e.py` → `eval/runner.py`（`run_suite`、`build_e2e_snapshot`）
- 快照组装：`eval/state_capture.py`
- 打分 CLI：`eval/score_run.py` → `eval/scoring.py`、`eval/scoring_llm.py`
- LLM 评委 Prompt：`src/agent/prompts/eval_judge_quality.md`

---

## 6. 前置条件

- `config/setting.yaml` 等能通过 `run_startup_configuration_check`（与主程序一致）。
- 打分若启用默认 **LLM 评委**：需配置可用的 LLM（与 `LLMFactory` / Settings 一致）；离线或只想规则分时使用 **`--no-llm`**。
