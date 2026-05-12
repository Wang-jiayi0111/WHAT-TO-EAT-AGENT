# WHAT-TO-EAT-AGENT

基于 **LangGraph** 的膳食对话助手：在**个人饮食约束**与**家庭食材库存**前提下，帮助用户决定「吃什么」、检索与解析菜谱、计算购物缺口，并在多意图场景下完成澄清与编排。

---

## 功能概览

- **意图分流与按需短路**：路由识别后按任务栈执行，避免固定全链路流水线。
- **菜谱检索与定稿**：经 **MCP** 对接本地 RAG（向量 + BM25 混合、可配置精排），菜谱结构化需求 **R** 以锁定文件后的解析管线为准。
- **库存与购物缺口**：库存查询、确认菜谱后的扣减、补货预览；**R − I** 预计算缺口并缓存，用户索要清单时优先返回缓存结果。
- **记忆与约束**：会话摘要、短期约束、用户画像（过敏原等硬约束）参与检索与生成。
- **终端对话入口**：`main.py` 提供交互式 CLI（Rich 状态提示）。

更完整的需求与架构约定见仓库内 **[《软件需求规格说明书》](docs/项目说明.md)** 与 **[《规格设计说明书》](docs/规格设计.md)**。

---

## 技术栈（摘要）

| 层级 | 选型 |
|------|------|
| 编排 | LangGraph（Checkpoint / 多节点工作流） |
| 检索 | Chroma、BM25（SQLite FTS）、RRF 融合、可选 Cross-Encoder 重排 |
| 工具协议 | MCP（stdio）— `src/mcp/server.py` |
| 配置 | `config/setting.yaml`（路径、LLM、MCP、检索等） |
| 本地数据 | SQLite（画像、库存、摄取历史等） |

实现细节与模块边界见 **[DEV_SPEC.md](DEV_SPEC.md)**。

---

## 快速开始

### 1. 环境

- 建议使用 **Python 3.10+** 与虚拟环境。
- 克隆仓库后，将项目根目录加入 `PYTHONPATH`（或在项目根执行命令），并按代码中的 `import` 安装依赖（常见包括 `langgraph`、`langchain-core`、`chromadb`、`mcp`、`rich`、`pyyaml` 等）。若后续仓库提供统一的 `requirements.txt` 或 `[project.dependencies]`，以该清单为准。

### 2. 配置

1. 对照 **[config/setting.yaml](config/setting.yaml)** 配置数据目录、向量库路径、**LLM**（如 DashScope 等）与 **MCP** 子进程启动参数。
2. 确保 `data/` 下菜谱、向量索引与数据库路径与配置一致；首次使用需完成数据摄取与索引构建（参见 `DEV_SPEC.md` / 摄取相关模块）。

### 3. 运行自检与对话

在项目根目录：

```bash
python main.py
```

启动前会执行 `run_startup_configuration_check`：自检失败时进程退出，请根据终端日志调整配置与数据路径。

---

## 效果评估（E2E）

本仓库对 **Agent 行为与质量** 的量化评估，以 **`eval/` 端到端用例集** 为权威入口：**采集固定用例的真实运行快照 → 分层自动打分（规则 + 可选 LLM 评委）→ 生成报告**。README **仅介绍该 E2E 体系**；**不把** `src.observability` 下的评测壳脚本作为项目效果的主口径（与 `eval/README.md` 中「两条线区别」的说明一致）。

### 如何跑全流程

```bash
# 1）跑用例并落盘采集（默认 eval/cases 下各 *.json）
python -m eval.run_e2e

# 2）将上一步输出的 run_id 代入打分（可开/关 LLM 评委，见 eval/README.md）
python -m eval.score_run --run-id <run_id>
```

主要产出：

- **机器可读**：`docs/evals/runs/<run_id>/scores.json`
- **分项报告**：`docs/evals/runs/<run_id>/scores_report.md`
- **总览（T-043）**：`docs/evals/runs/<run_id>/e2e_summary.md`，并可选更新根目录 **`docs/agent_eval_report.md`**

打分维度（默认权重以当次 `scores.json` / 报告为准）通常包括：**检索层**（金标召回、Hit@1、名次）、**生成层**、**对话层**；部分用例含 **购物清单断言层**。**效率类指标**（墙钟、Token、MCP 次数等）可在报告中查看，**默认不计入**加权总分（与总报告 §5.4 / §5.6 说明一致）。

详细参数、fixture 字段（如 `golden_recipe_ids`、`shopping_list_assert`）与 **`--no-llm`** 等开关，见 **[eval/README.md](eval/README.md)**。

### 示例性结果（非承诺值）

最近一次写入 **`docs/agent_eval_report.md`** 的 E2E run 中（具体 `run_id` 见该文件表头），在**小样本用例集**上曾得到约 **0.66** 的加权 **overall** 均值；失败索引多与「检索硬失败」等条目相关。实际分数随模型、数据、用例集与随机性变化，**以你本地跑出的 `scores.json` 为准**。

---

## 测试

```bash
pytest
```

`pyproject.toml` 中已配置 `testpaths = ["tests"]`。

---

## 仓库文档索引

| 文档 | 说明 |
|------|------|
| [docs/项目说明.md](docs/项目说明.md) | 需求基线（SRS） |
| [docs/规格设计.md](docs/规格设计.md) | 实现规格 |
| [DEV_SPEC.md](DEV_SPEC.md) | 开发规格与配置示例 |
| [eval/README.md](eval/README.md) | E2E 测评命令与分层指标说明 |

---

## 许可证

若根目录未包含 `LICENSE` 文件，使用前请自行与维护者确认授权范围。
