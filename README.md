# WHAT-TO-EAT-AGENT

基于 **LangGraph** 的家庭膳食决策与库存管理 Agent：在**本地菜谱库**、**个人饮食约束**与**家庭食材库存**这三个可控状态下，完成「找菜谱 → 锁定权威菜谱 → 解析食材需求 → 比对库存 → 生成购物缺口 / 扣减库存」的任务闭环。

本项目不是泛化的生活助理，而是一个边界清晰、可复现、可评测的 Agent 任务环境。系统围绕家庭做饭前后的真实决策链路展开：用户用自然语言提出吃什么、能不能做、缺什么、做完后更新库存等请求；Agent 通过受控工具读取本地知识库与数据库，在多轮对话中维护任务状态，并输出可执行的菜谱建议、澄清问题、购物清单或库存变更反馈。

## 项目定位

| 维度 | 内容 |
|------|------|
| **输入** | 用户自然语言请求，例如「我想做红烧肉，家里缺什么？」「最近肠胃不舒服，推荐一道清淡菜」「鸡蛋还剩多少？」「做完这道菜了，帮我扣库存」。 |
| **工具** | MCP 菜谱检索工具、菜谱源文件读取与结构化解析、本地 RAG（向量 + BM25）、SQLite 用户画像库、SQLite 家庭库存库、单位换算与缺口计算模块。 |
| **状态** | LangGraph 会话状态、`task_stack` 任务栈、会话摘要、短期约束、长期用户画像、锁定菜谱、结构化食材需求 **R**、库存快照 **I**、购物缺口缓存与错误/降级状态。 |
| **输出** | 菜谱候选与澄清问题、权威菜谱解析结果、结合约束的推荐理由、库存查询结果、购物缺口清单、补货预览、确认后的库存扣减反馈、可解释的降级回复。 |
| **验证** | `eval/` 固定用例集进行端到端采集与打分，覆盖检索、生成、对话、多意图、库存与购物清单等行为；报告落盘到 `docs/evals/` 与 `docs/agent_eval_report.md`。 |

---

## 功能概览

- **意图分流与按需短路**：路由识别后按任务栈执行，避免固定全链路流水线。
- **菜谱检索与定稿**：经 **MCP** 对接本地 RAG（向量 + BM25 混合、可配置精排），菜谱结构化需求 **R** 以锁定文件后的解析管线为准。
- **库存与购物缺口**：库存查询、确认菜谱后的扣减、补货预览；**R − I** 预计算缺口并缓存，用户索要清单时优先返回缓存结果。
- **记忆与约束**：会话摘要、短期约束、用户画像（过敏原等硬约束）参与检索与生成。
- **终端对话入口**：`main.py` 提供交互式 CLI（Rich 状态提示）。

更完整的需求与架构约定见仓库内 **[《软件需求规格说明书》](docs/项目说明.md)** 与 **[《规格设计说明书》](docs/规格设计.md)**。

---

## 上下文管理

Agent 不把全部历史对话直接塞进 Prompt，而是将上下文拆成可追溯的业务状态、可压缩的语义摘要与跨会话画像：

| 问题 | 策略 |
|------|------|
| **什么必须保留** | 当前任务栈、澄清候选、锁定菜谱、结构化食材需求 **R**、库存快照 **I**、购物缺口缓存、清单编辑层、写库确认状态、错误/降级状态、用户硬约束等结构化事实。 |
| **什么可以摘要** | 已完成或非阻塞的普通对话、推荐理由、解释过程、历史偏好描述等自然语言上下文，可压缩进 `conversation_summary`。 |
| **什么时候压缩** | 当会话消息数超过 `memory.summary.compress_trigger` 时，`conversation_summary` 节点压缩窗口外消息，仅保留最近 `memory.summary.window_size` 条原始消息；压缩不得清空 `task_stack`、`recipe_state`、`inventory_state` 等业务现场。 |


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
