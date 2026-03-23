## 6. 项目排期

### 6.1 **排期原则**

严格对齐本项目的架构分层与目录结构

- **模块化交付**：以 `src/agent`（LangGraph 逻辑）与 `src/mcp`（RAG 服务）为核心，双线并行。
- **1 小时一增量**：每个子任务必须包含“验收标准”与“测试方法”。
- **记忆优先**：由于本项目特色是“多成员画像”与“长短期记忆”，在基础 RAG 打通后立即切入记忆系统。

### 6.2 **阶段总览**

| **阶段**                                   | **总任务数** | **进度** | **状态** |
| ------------------------------------------ | ------------ | -------- | -------- |
| 阶段 A：工程骨架与测试基座                 | 3            | 0%       | [ ]      |
| 阶段 B：Libs 可插拔抽象层                  | 6            | 0%       | [ ]      |
| 阶段 C：膳食 Ingestion Pipeline (RAG 写入) | 8            | 0%       | [ ]      |
| 阶段 D：膳食 Retrieval Pipeline (RAG 读取) | 6            | 0%       | [ ]      |
| 阶段 E：MCP Server 接口开发                | 4            | 0%       | [ ]      |
| 阶段 F：记忆与库存系统 (Persistence)       | 6            | 0%       | [ ]      |
| 阶段 G：LangGraph Agent 编排 (The Brain)   | 7            | 0%       | [ ]      |
| 阶段 H：可视化 Dashboard 与追踪            | 6            | 0%       | [ ]      |
| 阶段 I：端到端验收与交付                   | 4            | 0%       | [ ]      |

- **阶段 A：工程骨架与测试基座**
  - **目的**：建立可运行、可配置、可测试的工程底座。
  - **核心任务**：初始化目录树，实现基于 `settings.yaml` 的配置加载器，并搭建 `pytest` 测试基座。
- **阶段 B：Libs 可插拔抽象层**
  - **目的**：定义核心组件的接口契约，实现“改配置不改代码”的组件切换。
  - **核心任务**：完成 LLM、Embedding、VectorStore 和 Reranker 的工厂模式实现，并补齐单位换算（Unit Converter）等膳食业务工具类。
- **阶段 C：膳食 Ingestion Pipeline（数据写入）**
  - **目的**：实现从原始 Markdown 菜谱到结构化向量存储的完整链路。
  - **核心任务**：开发支持标题层级切分的加载器，利用 LLM 自动提取食材 JSON、难度标签和摘要，并构建 BM25 倒排索引。
- **阶段 D：膳食 Retrieval Pipeline（数据读取）**
  - **目的**：实现高精准度的混合检索与业务过滤。
  - **核心任务**：开发查询预处理逻辑（同义词扩展），执行 Dense + BM25 的双路召回与 RRF 融合，并根据用户画像执行过敏原硬过滤。

- **阶段 E：MCP Server 接口开发**
  - **目的**：将菜谱知识库封装为标准的 MCP 协议工具，供 Agent 调用。
  - **核心任务**：实现 `search_recipes`（搜索）和 `get_recipe_details`（获取详情/食材清单）等原子化工具。
- **阶段 F：记忆与库存系统（持久化存储）**
  - **目的**：构建跨会话的家庭成员画像与实时库存感知能力。
  - **核心任务**：实现 `user_profiles.db`（偏好/禁忌）和 `inventory.db`（食材存量）的存储逻辑，并完成食材缺口的自动计算公式。

- **阶段 G：LangGraph Agent 编排（大脑构建）**
  - **目的**：利用状态机串联各专家节点，实现复杂的膳食决策逻辑。
  - **核心任务**：定义 `AgentState` 结构，编排意图路由（Router）、研究员（Researcher）、后勤主管（Logistics）和记忆守护者（Memory Keeper）的协作流转。
- **阶段 H：可视化 Dashboard 与追踪**
  - **目的**：实现全链路白盒化管理，解决 Agent 决策的“黑盒”问题。
  - **核心任务**：基于 Streamlit 搭建管理面板，提供库存管理界面、查询耗时瀑布图以及数据浏览功能。
- **阶段 I：端到端验收与收口**
  - **目的**：验证全链路闭环，确保“开箱即用”的工程质量。
  - **核心任务**：模拟真实用户进行多成员膳食推荐和采购清单生成的 E2E 测试，完成 RAG 质量定量评估并交付文档。

### 6.3 进度跟踪表

> **状态说明**：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成
>
> **更新时间**：每完成一个子任务后更新对应状态

#### 阶段 A：工程骨架与测试基座

**目的**：建立项目目录树、环境隔离、Pytest 基座及 `settings.yaml` 配置加载。

| **任务** | **任务名称** | **修改文件**                          | **实现类/函数**             | 状态 | **验收标准**                                   |
| -------- | ------------ | ------------------------------------- | --------------------------- | ---- | ---------------------------------------------- |
| A1       | 初始化目录树 | `main.py`, `src/**/__init__.py`       | -                           | [x]  | 能够成功执行 `import agent, mcp, ingestion`。  |
| A2       | 配置加载器   | `src/libs/base/settings.py`           | `Settings`, `load_settings` | [x]  | 能解析 YAML 并支持环境变量覆盖（如 API_KEY）。 |
| A3       | Pytest 基座  | `pyproject.toml`, `tests/conftest.py` | -                           | [x]  | 运行 `pytest` 显示 0 tests passed 而非报错。   |

#### 阶段 B：Libs 可插拔抽象层

**目的**：实现 LLM、Embedding、VectorStore 的工厂模式，屏蔽 Azure/Ollama 等不同供应商差异。

| **任务** | **任务名称**    | **修改文件**                       | **实现类/函数**             | 状态 | **验收标准**                                    |
| -------- | --------------- | ---------------------------------- | --------------------------- | ---- | ----------------------------------------------- |
| B1       | LLM 工厂        | `src/libs/adapters/llm/`           | `BaseLLM`, `LLMFactory`     | [ ]  | mock 测试能根据配置返回 OpenAI 或 Ollama 实例。 |
| B2       | Embedding 工厂  | `src/libs/adapters/embed/`         | `BaseEmbed`, `EmbedFactory` | [ ]  | 能够调用接口生成 1536 维（OpenAI）向量。        |
| B3       | Chroma 存储适配 | `src/libs/base/vector_store.py`    | `ChromaStore`               | [ ]  | 实现 `add` 和 `query` 的基础 CRUD。             |
| B4       | 单位换算中心    | `src/libs/utils/unit_converter.py` | `UnitConverter.normalize`   | [ ]  | 输入 "1kg" 和 "500g" 能统一为基准单位（g）。    |

#### 阶段 C：膳食 Ingestion Pipeline

**目的**：实现从 Markdown 菜谱到 Chroma + BM25 索引的完整链路。

| **任务** | **任务名称**  | **修改文件**                              | **实现类/函数**       | 状态 | **验收标准**                                                 |
| -------- | ------------- | ----------------------------------------- | --------------------- | ---- | ------------------------------------------------------------ |
| C1       | MD 结构化解析 | `src/ingestion/processors/loader.py`      | `MarkdownLoader`      | [ ]  | 提取 H1 作为菜名，H2（## 必备原料）作为核心元数据。          |
| C2       | 语义标题分块  | `src/ingestion/processors/splitter.py`    | `RecipeSplitter`      | [ ]  | 分块不切断“操作步骤”列表，保留标题上下文。                   |
| C3       | 增量哈希去重  | `src/libs/base/integrity.py`              | `SHA256Checker`       | [ ]  | 修改 MD 文件后能识别变更，未修改则跳过。                     |
| C4       | 食材标签提取  | `src/ingestion/processors/transformer.py` | `IngredientExtractor` | [ ]  | LLM 自动将“两克盐”转化为 `{"item": "盐", "amount": 2, "unit": "g"}`。 |
| C5       | BM25 索引构建 | `src/mcp/rag/bm25_engine.py`              | `SQLiteBM25Indexer`   | [ ]  | 在 `bm25_index.db` 中生成 FTS5 倒排索引。                    |

#### 阶段 D：膳食 Retrieval Pipeline

**目的**：实现混合检索、RRF 融合与基于画像的过滤。

| **任务** | **任务名称** | **修改文件**                | **实现类/函数**   | 状态 | **验收标准**                                       |
| -------- | ------------ | --------------------------- | ----------------- | ---- | -------------------------------------------------- |
| D1       | 查询预处理   | `src/mcp/rag/query_proc.py` | `QueryExpander`   | [ ]  | 将“番茄”扩展为“西红柿”，生成 BM25 Token。          |
| D2       | 混合检索调度 | `src/mcp/rag/engine.py`     | `HybridRetriever` | [ ]  | 并行触发 Vector 和 BM25 检索。                     |
| D3       | RRF 融合算法 | `src/mcp/rag/fusion.py`     | `RRFFusion`       | [ ]  | 按照排名倒数加权合并结果，输出确定性排名。         |
| D4       | 业务硬过滤   | `src/mcp/rag/engine.py`     | `MetadataFilter`  | [ ]  | 检索结果中若包含用户禁忌食材（花生等），自动剔除。 |

#### 阶段 E：MCP Server 接口开发 

**目的**：按 MCP 协议暴露 Tools，支持 Agent 调用。

| **任务** | **任务名称**   | **修改文件**        | **实现类/函数**      | 状态 | **验收标准**                                   |
| -------- | -------------- | ------------------- | -------------------- | ---- | ---------------------------------------------- |
| E1       | Stdio 协议处理 | `src/mcp/server.py` | `MCPServer.run`      | [ ]  | 使用 `mcp` SDK 建立通信，stdout 无污染。       |
| E2       | 搜索工具注册   | `src/mcp/tools.py`  | `search_recipes`     | [ ]  | Client 发送 JSON-RPC 能得到结构化结果。        |
| E3       | 详情提取工具   | `src/mcp/tools.py`  | `get_recipe_details` | [ ]  | 给定菜名，返回完整 Markdown 与归一化食材清单。 |

#### 阶段 F：记忆与库存系统

**目的**：实现 SQLite 持久化存储，支持多成员画像与库存计算。

| **任务** | **任务名称**   | **修改文件**                   | **实现类/函数**          | 状态 | **验收标准**                                            |
| -------- | -------------- | ------------------------------ | ------------------------ | ---- | ------------------------------------------------------- |
| F1       | 画像数据库实现 | `src/libs/base/db.py`          | `UserProfileDB`          | [ ]  | 成功创建 `user_profiles` 表，支持 JSON 存储禁忌。       |
| F2       | 库存管理逻辑   | `src/agent/nodes/logistics.py` | `InventoryManager`       | [ ]  | 实现库存扣减函数，并在 `inventory.db` 生效。            |
| F3       | 显式身份校准   | `src/agent/state.py`           | `update_active_user`     | [ ]  | 切换用户 ID 后，`active_constraints` 自动加载对应禁忌。 |
| F4       | 缺口计算公式   | `src/libs/utils/calc.py`       | `calculate_shopping_gap` | [ ]  | 执行 $R - I$，产出负值归零后的买菜清单。                |

#### 阶段 G：LangGraph Agent 编排

**目的**：构建状态机，实现各专家节点（研究员、后勤、记忆）的协同。

| **任务** | **任务名称**    | **修改文件**                       | **实现类/函数**     | 状态 | **验收标准**                                   |
| -------- | --------------- | ---------------------------------- | ------------------- | ---- | ---------------------------------------------- |
| G1       | 定义 AgentState | `src/agent/state.py`               | `AgentState`        | [ ]  | 包含 `logistics_buffer` 和 `task_stack` 字段。 |
| G2       | 意图路由节点    | `src/agent/nodes/router.py`        | `intent_router`     | [ ]  | 能识别“我想做饭”属于 `TASK_SEARCH`。           |
| G3       | 研究员节点      | `src/agent/nodes/researcher.py`    | `recipe_researcher` | [ ]  | 成功调用 MCP Client 获取检索结果。             |
| G4       | 记忆守护者节点  | `src/agent/nodes/memory_keeper.py` | `memory_keeper`     | [ ]  | 异步提取对话中的“不喜欢吃香菜”并存入 DB。      |
| G5       | 后勤主管节点    | `src/agent/nodes/logistics.py`     | `logistics_manager` | [ ]  | 根据 Researcher 的食材需求，生成差额清单。     |

#### 阶段 H：可视化 Dashboard 与追踪

**目的**：可视化管理，白盒化链路追踪。

| **任务** | **任务名称**      | **修改文件**                                     | **实现类/函数** | 状态 | **验收标准**                              |
| -------- | ----------------- | ------------------------------------------------ | --------------- | ---- | ----------------------------------------- |
| H1       | TraceContext 打点 | `src/observability/tracer.py`                    | `TraceContext`  | [ ]  | 每个请求生成 `trace_id`，记录各阶段耗时。 |
| H2       | 系统总览页        | `src/observability/dashboard/pages/overview.py`  | -               | [ ]  | 展示当前 LLM/Chroma 配置及各 DB 统计。    |
| H3       | 库存管理页        | `src/observability/dashboard/pages/inventory.py` | -               | [ ]  | 提供界面直接修改 `inventory.db` 存量。    |
| H4       | 链路追踪瀑布图    | `src/observability/dashboard/pages/traces.py`    | -               | [ ]  | 可视化展示检索与后勤计算的耗时分布。      |

#### 阶段 I：端到端验收与交付

**目的**：全链路回归测试与文档收口。

| **任务** | **任务名称**    | 状态 | **验收标准**                                                 |
| -------- | --------------- | ---- | ------------------------------------------------------------ |
| I1       | E2E：菜谱推荐流 | [ ]  | 输入“全家晚餐建议”，Agent 能综合考虑全员禁忌 + 冰箱库存给出方案。 |
| I2       | E2E：清单生成流 | [ ]  | 确认做菜后，Agent 自动扣减库存，并将缺失项列入清单。         |
| I3       | RAG 质量评估    | [ ]  | 运行 `rag_eval` 脚本，Hit Rate > 90%，Faithfulness > 0.8。   |
| I4       | 文档交付        | [ ]  | 补齐 `README.md` 安装步骤与 `settings.yaml` 配置示例。       |
