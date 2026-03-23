## 5.  系统架构与模块设计

### 5.1 项目架构图

```Plain
+=============================================================================+
|                      用户交互与可视化层 (User Interface)                     |
|         (Streamlit Dashboard: 数据浏览器 / 摄取管理 / 链路追踪)             |
+=============================================================================+
                                     |
                                     v
+=============================================================================+
|                      Agent 逻辑编排层 (Agent Orchestration)                 |
|            (LangGraph: 意图路由、状态机管理、短期线程记忆持久化)            |
+=============================================================================+
          |                  |                  |                  |
          v                  v                  v                  v
+------------------+ +------------------+ +------------------+ +--------------+
|   记忆守护者     | |     后勤主管     | |     澄清节点     | |   响应生成   |
| (Memory Keeper)  | | (Logistics Mgr)  | | (Clarify Node)   | | (Generator)  |
+------------------+ +------------------+ +------------------+ +--------------+
          |                  |                  |                  |
          +------------------+---------+--------+------------------+
                                       |
                                       v
+=============================================================================+
|                      跨协议通信层 (Protocol Bridge)                         |
|             (菜谱研究员 MCP Client <==> Stdio / JSON-RPC 2.0)               |
+=============================================================================+
                                       |
                                       v
+=============================================================================+
|                      知识服务层 (Knowledge Service)                    	   |
|              (MCP Server: 搜索工具、详情提取、安全核验工具)               		|
+=============================================================================+
                                       |
                                       v
+=============================================================================+
|                      RAG 执行与处理层 (RAG & Ingestion)              	       |
|            (混合检索、RRF 融合、语义重排、Markdown 离线处理流水线)        		  |
+=============================================================================+
                                       |
                                       v
+=============================================================================+
|                      数据存储层 (Persistence Layer)                      		|
|          (Chroma: 向量切片 | SQLite: 画像、库存、指纹、倒排索引)           		|
+=============================================================================+
```

```
+===================================================================================+
|                           MCP SERVER 核心架构 (RAG 知识中枢)                         |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                      通信传输层 (Transport Layer: Stdio)                      |  |
|  |  >> 标准输入 (stdin): 接收 JSON-RPC 指令 | << 标准输出 (stdout): 返回 MCP 协议消息 |  |
|  |  << 标准错误 (stderr): 输出系统日志与调试信息                                     |  |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|                                          V                                        |
|  +-----------------------------------------------------------------------------+  |
|  |                       工具注册与协议处理层 (MCP SDK / JSON-RPC)                 |  |
|  |  [ 工具集 (Tools Registry) ]                                                 |  |
|  |  ├─ search_recipes: 混合检索匹配片段       ├─ list_dietary_tags: 返回标签字典    |  |
|  |  └─ get_recipe_details: 获取全文与食材JSON └─ check_dietary_safety: 安全性交叉验证| |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|                                          V                                        |
|  +-----------------------------------------------------------------------------+  |
|  |                        RAG 检索流水线核心 (Retrieval Engine)                  |  |
|  |                                                                             |  |
|  |  1. [查询预处理]: 实体提取 (食材/工艺)、同义词扩展、Query 改写                     |  |
|  |                                       |                                     |  |
|  |  2. [并行召回]:                                                              |  |
|  |     ├─ 稠密路由 (Dense): 向量相似度检索 (Cosine)                                |  |
|  |     └─ 稀疏路由 (Sparse): BM25 关键词匹配检索                                   |  |
|  |                                       |                                     |  |
|  |  3. [结果融合]: RRF (Reciprocal Rank Fusion) 排名融合算法                      |  |
|  |                                       |                                     |  |
|  |  4. [重排与过滤] : 前置元数据硬过滤  + Cross-Encoder 深度语义重排                 |  |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|                                          V                                        |
|  +-----------------------------------------------------------------------------+  |
|  |                        响应封装层 (Response Composer)                         |  |
|  |  将检索结果封装为三位一体的 JSON 包:                                             |  |
|  |  - [Answer]: 基于切片生成的摘要总结                                             |  |
|  |  - [Structured Payload]: 归一化食材清单 (用于后勤计算)                           |  |
|  |  - [Metadata]: 溯源 ID、路径、禁忌标签、匹配分值                                 |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                                         V                                         |
|  +--------------------------------------+--------------------------------------+  |
|  |                         持久化存储层 (Storage Layer)                          |  |
|  |  +---------------------------------+      +---------------------------------+  |
|  |  |       向量库 (Chroma)            |      |      关系库 (SQLite / FTS5)      |  |
|  |  | - 稠密向量 (Dense Embeddings)    |      | - 倒排索引 (Sparse Index)         |  |
|  |  | - 元数据 (Metadata)              |      | - 摄取历史记录 (SHA256)           |  |
|  |  | - 原始切片文本 (Content Chunks)   |      | - 检索追踪日志 (Trace Logs)       |  |
|  +----------------------------------+      +-----------------------------------+  |
+==================================================================================+
```



### 5.2 目录结构

```Bash
WHAT_TO_EAT_AGENT/
├── config/                         # 配置文件目录
│   └── settings.yaml               # 全局组件配置 (如 LLM 供应商、向量库路径等)
├── data/                           # 持久化数据存储 (Local-First 核心)
│   ├── db/                         # SQLite 数据库集群
│   │   ├── ingestion_history.db    # 文件哈希指纹与增量摄取状态
│   │   ├── bm25_index.db           # FTS5 关键词倒排索引
│   │   ├── user_profiles.db        # 家庭成员长期画像与禁忌
│   │   ├── inventory.db            # 食材库存与余量追踪
│   │   └── checkpoints.db          # 对话线程状态持久化 (短期记忆)
│   ├── vector/                     # Chroma 向量数据库持久化文件
│   └── recipes/                    # 原始 Markdown 菜谱源文件
├── logs/                           # 追踪与运行日志
│   └── traces.jsonl                # 全链路结构化追踪日志 (JSON Lines)
├── src/                            # 源代码根目录
│   ├── agent/                      # Agent 逻辑层 (LangGraph 编排)
│   │   ├── graph.py                # 工作流定义与节点跳转逻辑
│   │   ├── state.py                # AgentState 结构化字典定义
│   │   ├── prompts/                # 节点Prompt设计
│   │   │   ├── router.yaml         # 总控路由的 System Prompt 及其任务描述
│   │   │   ├── researcher.yaml     # 菜谱研究员的检索与提取指令
│   │   │   ├── clarify.yaml        # 澄清节点的引导性追问模板
│   │   │   └── logistics.yaml      # 后勤主管的数值提取与计算指令
│   │   └── nodes/                  # 专家节点具体实现
│   │       ├── router.py           # 意图识别与任务分发
│   │       ├── researcher.py       # 菜谱研究员 (作为 MCP Client 交互)
│   │       ├── memory_keeper.py    # 记忆守护者 (偏好提取与同步)
│   │       ├── logistics.py        # 后勤主管 (库存比对与清单生成)
|   |       ├── clarify.py          # 澄清节点 (处理意图模糊)    
│   │       └── generator.py        # 最终响应生成
│   ├── mcp/                        # MCP Server 层 (独立 RAG 服务)
│   │   ├── server.py               # MCP Server 入口与通信协议处理
│   │   ├── tools.py                # 对外暴露的工具接口 (search_recipes 等)
│   │   └── rag/                    # RAG 核心流水线
│   │       ├── engine.py           # 检索流水线主控，协调混合召回、Fusion 融合与重排调度
│   │       ├── bm25_engine.py      # 基于 SQLite FTS5 的关键词检索引擎，负责倒排索引维护
│   │       ├── fusion.py           # 排名融合算法，实现 RRF 加权融合
│   │       ├── query_proc.py       # 查询预处理器，执行实体提取、同义词扩展与指代消歧
│   │       └── reranker.py         # 语义重排适配器， Cross-Encoder 与 LLM Rerank 切换
│   ├── ingestion/                  # 数据摄取流水线 (Ingestion Pipeline)
│   │   ├── pipeline.py             # 摄取任务编排 (Load->Split->Embed)
│   │   ├── document_manager.py     # 跨存储协调管理器 (负责全链路删除)
│   │   └── processors/             # 核心处理器
│   │       ├── loader.py           # Markdown 结构化解析
│   │       ├── splitter.py         # 语义感知的标题层级切分
│   │       └── transformer.py      # 语义增强、标签提取与摘要生成
│   ├── observability/              # 可观测性模块
│   │   ├── tracer.py               # TraceContext 追踪上下文机制
│   │   └── dashboard/              # Streamlit 可视化平台
│   │       ├── app.py              # Dashboard 主程序入口
│   │       └── pages/              # 多页面应用 (追踪、数据浏览、管理)
│   └── libs/                       # 通用基础库与抽象层
│       ├── adapters/               # 厂商适配器 (Azure/OpenAI/Ollama)
│       ├── base/                   # 抽象基类定义 (契约层)
│       │   ├── settings.py         # 全局配置加载与校验，支持环境变量覆盖
│       │   ├── integrity.py        # 基于 SHA256 的文件指纹校验，实现增量摄取
│       │   └── vector_store.py     # 向量数据库抽象基类，定义向量 CRUD 契约
│       └── utils/                  # 工具类 (单位换算中心 Unit Converter 等)
│           ├── unit_converter.py   # 单位标准化换算中心（如：克、两、勺的归一化）
│           └── calc.py             # 后勤计算引擎（如：执行库存缺口 R - I 公式）
├── tests/                               # 测试目录
│   ├── unit/                            # 单元测试
│   │   ├── test_dense_retriever.py      # 稠密检索器测试
│   │   ├── test_sparse_retriever.py     # 稀疏检索器测试
│   │   ├── test_fusion_rrf.py           # RRF 融合测试
│   │   ├── test_reranker_fallback.py    # Reranker 回退测试
│   ├── integration/                     # 集成测试
│   │   ├── test_ingestion_pipeline.py
│   │   ├── test_hybrid_search.py        # 混合检索集成测试
│   │   └── test_mcp_server.py           # MCP 服务器集成测试
│   └── e2e/                             # 端到端测试
│       ├── test_data_ingestion.py
│       ├── test_recall.py               # 召回回归测试
│       └── test_mcp_client.py           # MCP Client 模拟测试
├── .env                            # 环境变量 (存储 API Key)
├── requirements.txt                # 依赖清单
└── README.md                       # 项目启动与使用说明
```

### 5.3 模块说明

####  5.3.1 Agent逻辑层 (`src/agent/`)

| 模块                                              | 职责                                                         | 关键技术点                                                   |
| ------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [graph.py](http://graph.py)                       | 工作流编排。定义 Agent 的节点跳转逻辑与执行流向。            | LangGraph 状态机、节点转移条件定义。                         |
| [state.py](http://state.py)                       | 状态模型定义。规定跨节点流转的 AgentState 数据结构。         | task_stack 任务栈、logistics_buffer 缓冲区。                 |
| prompts/*.md                                      | Prompt 资产管理。实现指令与代码逻辑的物理隔离。              | Markdown 格式存储。                                          |
| nodes/[router.py](http://router.py)               | 意图路由总控。分析查询并分发至后续专家节点。                 | CoT 任务拆解、intent_tag 任务原子化分解。                    |
| nodes/[researcher.py](http://researcher.py)       | 菜谱研究员 (MCP Client)。向 Server 发起 RAG 检索并解析数据。 | MCP Client 协议调用、切片级与文档级二段式检索。              |
| nodes/[memory_keeper.py](http://memory_keeper.py) | 记忆守护者。静默提取并持久化用户长期偏好与画像。             | 被动提取机制、画像标签化分层、冲突时效仲裁。                 |
| nodes/[logistics.py](http://logistics.py)         | 后勤主管。执行库存比对，动态生成与维护买菜清单。             | 缺口计算公式 $Shopping_list = max(0, R-I)$、自动抵扣逻辑。   |
| nodes/[clarify.py](http://clarify.py)             | 澄清节点。当意图识别置信度较低时发起主动追问。               | 意图置信度阈值判定、引导性交互指令。                         |
| nodes/[generator.py](http://generator.py)         | 响应生成节点。将专家节点（研究员、后勤主管）填充的结构化字段，根据意图标签组装成自然语言反馈 。 | 意图驱动的响应策略（如直接闲聊、菜谱推荐、清单汇报）、多源数据融合（Expert Payloads）、带引用的内容生成 。 |

####  5.3.2  MCP Server 层 (`src/mcp/`)

| 模块                              | 职责                                                   | 关键技术点                                       |
| --------------------------------- | ------------------------------------------------------ | ------------------------------------------------ |
| [server.py](http://server.py)     | MCP Server 入口。处理 Stdio Transport 通信与协议握手。 | Python MCP SDK、JSON-RPC 2.0 消息处理。          |
| [tools.py](http://tools.py)       | 对外工具接口。实现 search_recipes 等原子化工具函数。   | Structured Payload 食材清单 JSON 封装。          |
| [engine.py](http://engine.py)     | RAG 检索引擎。调度多路召回并在知识库中执行匹配。       | 混合检索 (Dense + BM25)、RRF 排名融合算法。      |
| [reranker.py](http://reranker.py) | 语义精排后端。对召回候选集进行高精度二次排序。         | Cross-Encoder 深度打分、超时自动 Fallback 机制。 |

####  5.3.3 数据摄取流水线 (`src/ingestion/`)

| 模块                                              | 职责                                                  | 关键技术点                                   |
| ------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------- |
| [pipeline.py](http://pipeline.py)                 | 摄取流程调度。串联加载、切分、增强与向量化写入环节。  | 批处理优化、Pipeline 进度回调机制。          |
| [document_manager.py](http://document_manager.py) | 跨存储协调器。确保文件、向量及索引的全链路对账删除。  | 协调 Chroma、BM25 与 SQLite 的同步更新。     |
| [loader.py](http://loader.py)                     | Markdown 解析器。提取文档结构、标题层级与文件指纹。   | 前置 SHA256 指纹去重、业务元数据设计抽取。   |
| [splitter.py](http://splitter.py)                 | 智能分块组件。基于标题层级进行语义感知的文档切分。    | 递归切分策略、全局业务元数据透传。           |
| [transformer.py](http://transformer.py)           | 语义增强转换。利用 LLM 自动提取摘要、食材标签与难度。 | 智能重组去噪、语义元数据注入、独立重试机制。 |

####  5.3.4 辅助与基础设施层 (`src/libs/` & `observability/`)

| 模块                          | 职责                                                   | 关键技术点                                     |
| ----------------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| adapters/                     | 厂商多态适配。屏蔽不同 LLM 与 Embedding 供应商的差异。 | 工厂模式、统一 chat() 与 embed() API 接口。    |
| utils/                        | 单位换算中心。将菜谱中的模糊用量归一化为基准库存单位。 | Unit Converter 标准化换算逻辑。                |
| [tracer.py](http://tracer.py) | 追踪记录器。捕获请求全生命周期的耗时、中间变量与状态。 | trace_id 全局关联、JSON Lines 异步日志持久化。 |
| dashboard/                    | 可视化管理平台。提供数据浏览、Query 追踪与评估面板。   | Streamlit 多页面渲染、实时摄取进度展示。       |

####  5.3.5 本地数据存储 (`data/`)

| 数据库文件           | 存储内容与业务作用                                           |
| -------------------- | ------------------------------------------------------------ |
| ingestion_history.db | 记录已处理菜谱文件的唯一标识，实现零成本的增量更新，防止重复索引 。 |
| bm25_index.db        | 基于 SQLite FTS5 插件的关键词倒排索引，用于精确食材对账。    |
| inventory.db         | 维护食材标准名称、当前库存量、单位及过期预警。               |
| user_profiles.db     | 长期成员画像存储。构建跨会话持久化的多成员档案。             |
| checkpoints.db       | 持久化对话线程的 AgentState，支持服务重启后的记忆恢复。      |

### 5.4 数据流说明

####  5.4.1 离线数据摄取流程

```Plain
+=======================+
|  原始菜谱资源 (.md)   | ----> [ 路径: data/recipes/ ]
+=======================+
           |
           V
+-----------------------+       +---------------------------+
|    Markdown Loader    | <---> |   ingestion_history.db    |
| (解析格式、提取 H1)   |       | (SHA256 校验 & 增量过滤)  |
+-----------------------+       +---------------------------+
           |
           V
+-----------------------+
|    智能分块组件       | ----> [ 基于 Markdown 标题层级切分 ]
| (Smart Splitter)      | ----> [ 保证步骤完整性与元数据透传 ]
+-----------------------+
           |
           V
+-----------------------+       +---------------------------+
|   LLM 语义增强        | <---> |      LLM 推理后端         |
| (Transformer)         |       | (提取食材 JSON、标签、摘要)|
+-----------------------+       +---------------------------+
           |
           V
+-----------------------+       +---------------------------+
|   双路向量化计算      | ----> | Dense: 稠密语义向量 (语义) |
| (Dual Embedding)      | ----> | Sparse: 稀疏关键词权重 (BM25)|
+-----------------------+       +---------------------------+
           |
           V
+===========================================================+
|                   持久化存储层 (Storage)                  |
|                                                           |
|  +---------------------+        +----------------------+  |
|  |   Chroma 向量库     |        |   bm25_index.db      |  |
|  | (存储向量与富元数据)|        | (SQLite FTS5 倒排索引)|  |
|  +---------------------+        +----------------------+  |
+===========================================================+
```

####  5.4.3 MCP Server

```Plain
用户查询 (via MCP Client)
               |
               V
+-----------------------------+
|      MCP Server 入口        | ----> [ JSON-RPC 解析 ]
|      (Stdio Transport)      | ----> [ 路由至 search_recipes 工具 ]
+--------------+--------------+
               | query + params (filters, top_k)
               V
+-----------------------------+
|     Query Processor         | ----> [ 关键词提取 / 同义词扩展 ]
|      (查询预处理器)         | ----> [ 提取 Metadata 过滤条件 ]
+--------------+--------------+
               | processed_query + filters
               V
+===========================================================+
|                   Hybrid Search (混合检索)                |
|                                                           |
|  +---------------------+           +-------------------+  |
|  |   Dense Retrieval   |           |  Sparse Retrieval |  |
|  |     (Embedding)     | <智能并行> |      (BM25)       |  |
|  +----------+----------+           +---------+---------+  |
|             |                                |            |
|             V                                V            |
|  +-----------------------------------------------------+  |
|  |                  Fusion (RRF 融合)                   |  |
|  |           (合并两路得分，生成 Top-M 候选集)            |  |
|  +--------------------------+--------------------------+  |
+=============================|=============================+
                              | Top-M 候选切片
                              V
+-----------------------------+
|      Semantic Rerank        | ----> [ 使用 Cross-Encoder 精排 ]
|       (语义重排器)          | ----> [ 剔除低相关度 / 冗余切片 ]
+--------------+--------------+
                              | 最终精选切片 (Top-K)
                              V
+-----------------------------+       +---------------------+
|    Response Generator       | <---> |   Internal Prompt   |
|     (Server 侧生成)          |       | (注入溯源与结构化指令)|
+--------------+--------------+       +---------------------+
               |
               V
+===========================================================+
|                   MCP Response 封装返回                   |
|                                                           |
|  1. [Answer]: 带引用的自然语言摘要                        |
|  2. [Payload]: 归一化的结构化食材清单 (JSON)              |
|  3. [Metadata]: 原始文档溯源信息                          |
+===========================================================+
```

### 5.5 配置驱动设计

```YAML
# 全局路径管理
paths:
  data_dir: "./data"
  db_dir: "./data/db"
  vector_store: "./data/vector/chroma"
  recipes_dir: "./data/recipes"
  log_dir: "./logs"

# MCP Server 交互配置 (Agent 调用 Server 的凭证)
mcp:
  transport: "stdio"          # stdio | http
  command: "python"           # 启动 server 的命令
  args: ["src/mcp/server.py"] # server 入口路径
  env:                        # 传递给子进程的环境变量
    PYTHONPATH: "."

# 离线摄取流水线配置
ingestion:
  chunk_size: 1000            # 基于字符或标记的切块大小
  chunk_overlap: 100          # 块之间重叠大小
  enrichment:                 # Transformer 阶段配置
    use_llm_summary: true     # 是否调用 LLM 生成切片摘要
    extract_metadata: true    # 是否自动提取食材标签/难度

# 检索与 RAG 核心
retrieval:
  sparse_backend: bm25
  fusion_algorithm: rrf
  top_k_dense: 20
  top_k_sparse: 20
  top_k_final: 10
  rerank:
    enabled: true             # 增加开关，方便调试时跳过精排
    backend: cross_encoder 
    model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
    threshold: 0.5            # 丢弃低于该分的检索结果

# 本地业务数据库配置 (SQLite)
databases:
  user_profiles: "user_profiles.db"
  inventory: "inventory.db"
  ingestion_history: "ingestion_history.db"
  
# LLM 配置
llm:
  provider: dashscope             # 标识供应商为阿里云百炼 (DashScope)
  model: qwen3-max                # 2026年旗舰级模型标识符
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1" # 百炼的 OpenAI 兼容端点
  api_key: "${DASHSCOPE_API_KEY}" # 从环境变量读取 API KEY
  
  # 运行参数调优
  temperature: 0.7                # 创意与严谨的平衡
  max_tokens: 2000                # 单次生成最大长度
  timeout: 60                     # 旗舰模型推理较重，建议增加超时阈值
  retry_limit: 3                  # 遇到网络抖动自动重试

# Embedding 配置
embedding:
  provider: openai          # openai | azure | ollama (本地)
  model: text-embedding-3-small
  
# Vision LLM 配置 (图片描述)
vision_llm:
  provider: azure           # azure | dashscope (Qwen-VL)
  model: gpt-4o
  
# 向量存储配置
vector_store:
  backend: chroma           # chroma | qdrant | pinecone
  persist_path: ./data/db/chroma

# 检索配置
retrieval:
  sparse_backend: bm25      # bm25 | elasticsearch
  fusion_algorithm: rrf     # rrf | weighted_sum
  top_k_dense: 20
  top_k_sparse: 20
  top_k_final: 10

# 重排配置
rerank:
  backend: cross_encoder    # none | cross_encoder | llm
  model: cross-encoder/ms-marco-MiniLM-L-6-v2
  top_m: 30

# 评估配置
evaluation:
  backends: [ragas, custom]
  golden_test_set: ./tests/fixtures/golden_test_set.json

# 可观测性配置
observability:
  enabled: true
  log_file: ./logs/traces.jsonl

# Dashboard 管理平台配置
dashboard:
  enabled: true
  port: 8501                     # Streamlit 服务端口
  traces_dir: ./logs             # Trace 日志文件目录
  auto_refresh: true             # 是否自动刷新（轮询新 trace）
  refresh_interval: 5            # 自动刷新间隔（秒）
```
