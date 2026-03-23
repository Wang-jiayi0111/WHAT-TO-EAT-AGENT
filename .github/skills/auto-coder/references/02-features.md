## 2. 核心特点

### **2.1 RAG 策略与设计亮点**

本项目在 RAG 链路的关键环节采用了经典的工程化优化策略，平衡了检索的查准率与查全率，具体思想如下：

- **分块策略 (Chunking Strategy)**：采用智能分块与上下文增强，为高质量检索打下基础。
  - **Markdown 结构化分块：**摒弃定长切分，利用 Markdown 标题层级（## 必备原料、## 操作）进行语义感知切分，确保烹饪步骤的完整性；
  - **上下文增强**：为 Chunk 注入文档元数据，确保检索时不仅匹配文本，还能感知上下文。
- **粗排召回 (Coarse Recall / Hybrid Search)**：采用 **混合检索** 策略作为第一阶段召回，快速筛选候选集。
  - 结合 **稀疏检索 (Sparse Retrieval/BM25)** 利用关键词精确匹配，解决专有名词查找问题；
  - 结合 **稠密检索 (Dense Retrieval/Embedding)** 利用语义向量，解决同义词与模糊表达问题；
  - 两者互补，通过 RRF (Reciprocal Rank Fusion) 算法融合，确保查全率与查准率的平衡。
- **精排重排 (Rerank / Fine Ranking)**：在粗排召回的基础上进行深度语义排序。
  - 采用 Cross-Encoder（专用重排模型）或 LLM Rerank（可选后端）对候选集进行逐一打分，识别细微的语义差异。
    - 通过 **"粗排(低成本泛召回) -> 精排(高成本精过滤)"** 的两段式架构，在不牺牲整体响应速度的前提下大幅提升 Top-Results 的精准度。

### **2.2 全链路可插拔架构 (Pluggable Architecture)**

鉴于 AI 技术的快速演进，本项目在架构设计上追求**极致的灵活性**，拒绝与特定模型或供应商强绑定。**整个系统**（不仅是 RAG 链路）的每一个核心环节均定义了抽象接口，支持"乐高积木式"的自由替换与组合：

- **LLM 调用层插拔 (LLM Provider Agnostic)**：

  - 核心推理 LLM 通过统一的抽象接口封装，支持**多协议**无缝切换：

    - **Azure OpenAI**：企业级 Azure 云端服务，符合合规与安全要求；
    - **OpenAI API**：直接对接 OpenAI 官方接口；
    - **本地模型**：支持 Ollama、vLLM、LM Studio 等本地私有化部署方案；
    - **其他云服务**：DeepSeek、Anthropic Claude 等第三方 API。

    通过配置文件一键切换后端，**零代码修改**即可完成 LLM 迁移，便于成本优化、隐私合规或 A/B 测试。

- **Embedding & Rerank 模型插拔 (Model Agnostic)**：
  - Embedding 模型与 Rerank 模型同样采用统一接口封装；
  - 支持云端服务（OpenAI Embedding, Cohere Rerank）与本地模型（Sentence-Transformers, BGE）自由切换。

- **RAG Pipeline 组件插拔**：
  - **Loader（解析器）**：支持 PDF、Markdown、Code 等多种文档解析器独立替换
  - **Smart Splitter（切分策略）**：语义切分、定长切分、递归切分等策略可配置；
  - **Transformation（元数据/图文增强逻辑）**：OCR、Image Captioning 等增强模块可独立配置。

- **检索策略插拔 (Retrieval Strategy)**：
  - 支持动态配置纯向量、纯关键词或混合检索模式；
  - 支持灵活更换向量数据库后端（如从 Chroma 迁移至 Qdrant、Milvus）。

- **评估体系插拔 (Evaluation Framework)**：
  - 评估模块不锁定单一指标，支持挂载不同的 Evaluator（如 Ragas, DeepEval）以适应不同的业务考核维度。

### 2.3 MCP 生态集成 (Copilot / ReSearch)

本项目的核心设计完全遵循 Model Context Protocol (MCP) 标准，这使得它不仅是一个独立的问答服务，更是一个即插即用的知识上下文提供者。

- **工作原理**：
  - 我们的 Server 作为一个 **MCP Server** 运行，暴露一组标准的 `tools` 和 `resources` 接口。
  - 任何兼容的**MCP Clients**（如 GitHub Copilot, ReSearch Agent, Claude Desktop 等）均可直接调用该“膳食知识库”server。
  - **无缝接入**：当你在 GitHub Copilot 中提问时，Copilot 作为一个 MCP Host，能够自动发现并调用我们的 Server 提供的工具（如 `search_documentation`），获取我们内置的私有文档知识，然后结合这些上下文来回答你的问题。
- **优势**：
  - **零前端开发**：无需为知识库开发专门的 Chat UI，直接复用开发者已有的编辑器（VS Code）和 AI 助手。
  - **上下文互通**：Copilot 可以同时看到你的代码文件和我们的知识库内容，进行更深度的推理。
  - **标准兼容**：任何支持 MCP 的 AI Agent（不仅是 Copilot）都可以即刻接入我们的知识库，一次开发，处处可用。

### 2.4 可观测性、可视化管理与评估体系 (Observability, Visual Management & Evaluation)

针对 RAG 系统常见的“黑盒”问题，本项目致力于让每一次生成过程都**透明可见**且**可量化**，并提供完整的**本地可视化管理平台**：

- **全链路白盒化 (White-box Tracing)**：
  - 记录并可视化 RAG 流水线的每一个中间状态：覆盖 Ingestion（加载→切分→增强→编码→存储）与 Query（查询预处理→Dense/Sparse 召回→融合→重排→响应构建）两条完整链路。
  - 开发者可以清晰看到“系统为什么选了这个文档”以及“Rerank 起了什么作用”，从而精准定位坏 Case。
- **可视化管理平台 (Visual Management Dashboard)**：
  - 基于 Streamlit 的本地 Web 管理面板，提供六大功能页面：
    - **系统总览**：展示当前可插拔组件配置（LLM/Embedding/Splitter/Reranker）与数据资产统计。
    - **数据浏览器**：查看已索引的文档列表、Chunk 详情（原文、metadata 各字段、关联图片），支持搜索过滤。
    - **Ingestion 管理**：通过界面选择文件触发摄取、实时展示各阶段进度、支持删除已摄入文档（跨 4 个存储的协调删除）。
    - **Query 追踪**：查询历史列表，耗时瀑布图，Dense/Sparse 召回对比，Rerank 前后排名变化。
    - **Ingestion 追踪**：摄取历史列表，各阶段耗时与处理详情。
    - **评估面板**：运行评估任务、查看各项指标、历史趋势对比。
  - 所有页面基于 Trace 中的 `method`/`provider` 字段**动态渲染**，更换可插拔组件后 Dashboard 自动适配，无需修改代码。
- **自动化评估闭环 (Automated Evaluation)**：
  - 集成 Ragas 等评估框架（可插拔），为每一次检索和生成计算“体检报告”（如召回率 Hit Rate、准确性 Faithfulness 等指标）。
  - 拒绝“凭感觉”调优，建立基于数据的迭代反馈回路，确保每一次策略调整（如修改 Chunk Size 或更换 Reranker）都有量化的分数支撑。

### 2.5 上下文记忆系统(Persistent Context)

本项目针对家庭多成员场景，设计了**分层持久化记忆系统**

- **多维度用户画像 (Layered User Profiling) ：**
  - **基础档案：** 存储多成员的生理指标（身高、体重、目标热量）与核心禁忌（过敏源、疾病忌口）。
  - **动态偏好：** 记录口味倾向（如：偏爱酸辣、拒绝香菜）和烹饪习惯（如：早晨通常只有10分钟准备时间）。
  - **显式身份校准 (Explicit Identity Alignment)：** 系统提供成员切换接口（支持 UI 按钮点击），允许用户主动校准当前身份。
  - **多成员冲突处理：** 当 Agent 为多人准备膳食时（如“做全家人的晚餐”），Logistics Manager 节点会自动执行 **Intersection (交集)** 逻辑
- **长短期记忆解耦 (Memory Decoupling)：**
  - **短期工作记忆 (Thread-based Memory)：** 基于 LangGraph 的 Checkpointer 机制，保留当前对话的上下文，支持“多加两瓶牛奶”等即时指令的追溯。
  - **长期语义记忆 (Semantic Long-term Memory)：** 由 **Memory Keeper** 节点定期将对话中的关键信息转化为结构化标签存入数据库，不随对话结束而丢失。
- **家庭共享库存感知 (Shared Inventory Awareness)：**
  - Agent 会持续追踪家庭库存的变动，在生成清单时自动抵扣剩余食材。
- **被动式提取机制 (Passive Extraction)：**
  - 无需用户手动设置，Agent 能够从自然对话中隐式学习。例如，当用户多次提到“最近牙齿不太好”时，Agent 会自动将“软烂易消化”标记为当前阶段的高优先级偏好。

### 2.6 Agent逻辑解耦

本项目将Agent的相关功能模块作为独立节点，并由一个**总控节点**进行**意图识别**激活对应节点：

- **Memory Keeper (记忆守护者):** 专门负责从对话中静默提取偏好，并更新数据库。它不直接回答用户，只负责维护“人设”。
- **Recipe Researcher (菜谱研究员):** 专门负责 MCP Server 的 RAG 检索，将 Markdown 转化为结构化数据。
- **Logistics Manager (后勤主管):** 专门负责库存比对和清单生成。
