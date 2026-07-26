# RAG Backend — 本地知识库混合检索问答系统

> 基于 FastAPI + LangChain + FAISS + DashScope 的本地知识库问答后端。
> 采用 **稠密向量 + BM25 稀疏检索 + RRF 融合 + Cross-Encoder 精排** 的两阶段检索架构，配合 Cross-Encoder 精排保证上下文质量；消融实验表明精排阶段是回答质量的最大单一贡献者（详见 [eval/](eval/)）。

---

## 一、整体架构

```
┌──────────────┐  upload   ┌────────────────────────┐  embed   ┌──────────────┐
│  Frontend    │ ────────► │ doc_parser → splitter  │ ───────► │ FAISS index  │
│  (Vue 3)     │           │ (PDF/DOCX/MD/TXT)      │          │ + chunks.json│
└──────┬───────┘           └────────────────────────┘          └───────┬──────┘
       │                                                               │
       │ POST /api/chat/stream                                         │
       ▼                                                               │
┌──────────────────────────────────────────────────────────────────────┴───────┐
│                          Retriever.search(query)                              │
│  ┌────────────────┐    ┌────────────────┐                                     │
│  │ FAISS (top 20) │    │ BM25  (top 20) │   ← 两路并行召回                    │
│  └───────┬────────┘    └───────┬────────┘                                     │
│          └──────────┬──────────┘                                              │
│                     ▼                                                         │
│            RRF Fusion (k=60)        ← 排名融合，与分数尺度无关                │
│                     ▼                                                         │
│      gte-rerank Cross-Encoder       ← 精排，输出 0..1 相关性分数              │
│                     ▼                                                         │
│      threshold=0.2 过滤 → Top-K=3   ← 宁可没答案，不要错答案                  │
└─────────────────────┬─────────────────────────────────────────────────────────┘
                      ▼
              Prompt(context + query)
                      ▼
           qwen-turbo streaming → NDJSON → 前端逐 token 渲染
```

---

## 二、技术决策表（Why this, not that）

| 决策点 | 现选型 | 备选 | 选这个的原因 |
|---|---|---|---|
| 向量模型 | DashScope `text-embedding-v3` (1024d) | OpenAI ada-002 (1536d) / bge-large-zh / m3e | 中文场景 C-MTEB 表现优于 ada-002；国内调用稳定低延迟；与 qwen 同生态便于配套 |
| 向量数据库 | LangChain FAISS（`IndexFlatL2`）| Qdrant / Milvus / Chroma | 百级文档量暴力检索召回率 100%，无 IVF/HNSW 调参成本；预留扩展点 |
| 稀疏检索 | `rank_bm25` + `jieba.lcut` | ES / Lucene | 单机部署简单，无外部依赖；jieba 处理 CJK 分词 |
| 融合算法 | **RRF（k=60）** | 加权融合（线性组合）| BM25 分数无界、余弦相似度 [0,1]，量级无法直接加权；RRF 只用 rank 信息，对分数尺度免疫；k=60 为 Cormack et al. 2009 SIGIR 工业默认值 |
| 精排 | DashScope `qwen3-rerank` (cross-encoder) | bge-reranker 本地 / ColBERT | bi-encoder 召回 40 个 → cross-encoder 精排到 3 个，平衡 latency 与 accuracy；DashScope 托管减少部署负担 |
| 相关性阈值 | `0.2` | 不设 / 更高 | 宁可空答案也不喂低相关 chunk 给 LLM，降低幻觉的最后一道闸门 |
| 切片策略 | `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter`（500/50）| 固定窗口 / 语义切片 | Markdown 先按 H1/H2/H3 切，保留结构语义；500 字符兼顾召回粒度与上下文完整性 |
| LLM | `qwen3.7-plus`（yaml 可切换） | qwen-turbo / qwen-max | 上下文已压缩到 Top-3 chunk，中档模型即可；成本敏感场景可降至 qwen-turbo（2026-05 评估基线即用 turbo） |
| 流协议 | NDJSON over HTTP（FastAPI StreamingResponse）| 标准 SSE / WebSocket | 复用 HTTP 基础设施；逐行 JSON 解析比标准 SSE 帧解析更直观 |

---

## 三、配置一览（`app/core/config.py` 默认值）

```python
# 模型
EMBEDDING_MODEL = "text-embedding-v3"
LLM_MODEL = "qwen3.7-plus"
RERANK_MODEL = "qwen3-rerank"

# 切片
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# 检索
TOP_K = 3                  # 最终喂 LLM 的 chunk 数
VECTOR_CANDIDATES = 20     # FAISS 召回候选
BM25_CANDIDATES = 20       # BM25 召回候选
ENABLE_HYBRID = True       # 混合检索
ENABLE_RERANK = True       # 精排
RRF_K = 60                 # RRF 平滑常数
RELEVANCE_THRESHOLD = 0.2  # 精排分数下限
```

可通过 `config/app.yaml` 覆盖默认值，无需改代码。

---

## 四、API 端点

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传文档（PDF/DOCX/MD/TXT） |
| GET  | `/api/docs/list` | 已索引文档列表 |
| POST | `/api/docs/reindex/{doc_id}` | 单文档重新向量化 |
| GET  | `/api/docs/content/{doc_id}` | 获取原文 |
| GET  | `/api/docs/file/{doc_id}` | 下载原始文件 |
| DELETE | `/api/docs/{doc_id}` | 删除文档 + 清理向量 |
| POST | `/api/chat/stream` | 流式问答（NDJSON：steps / sources / answer chunks） |
| GET  | `/api/status` | 系统健康检查 |

启动后访问 `http://localhost:8000/docs` 查看 Swagger。

---

## 五、快速开始

### 1. 环境

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) 包管理器（推荐）

### 2. 配置

在 `rag-backend/` 创建 `.env`：

```env
DASHSCOPE_API_KEY=your_api_key_here
```

如需调整模型/检索参数，编辑 `config/app.yaml`。

### 3. 安装 & 启动

```bash
cd rag-backend
uv sync                    # 安装依赖
uv run start.py            # 启动服务（0.0.0.0:8000）
```

### 4. 启动前端

```bash
cd ../rag-frontend
npm install
npm run dev                # http://localhost:5173
```

---

## 六、目录结构

```
rag-backend/
├── app/
│   ├── api/                  # FastAPI 路由
│   │   ├── docs.py           # 文档 CRUD
│   │   └── chat.py           # 流式问答端点
│   ├── services/
│   │   ├── doc_service.py    # 解析 → 切片 → Embedding → FAISS
│   │   ├── retriever.py      # 混合检索 + RRF + Rerank 核心
│   │   └── chat_service.py   # 检索结果 → Prompt → LLM
│   ├── utils/
│   │   └── doc_parser.py     # PDF/DOCX/MD/TXT 多格式解析
│   ├── schemas/              # Pydantic 模型
│   ├── core/config.py        # 配置（.env + YAML）
│   └── main.py               # FastAPI 入口
├── config/app.yaml           # 运行时配置
├── data/
│   ├── docs/                 # 原始文件（UUID 命名）
│   ├── vector_db/            # FAISS index 落盘
│   └── chunks_corpus.json    # 全量 chunk 元数据
├── eval/                     # RAGAS 风格离线评估（见 eval/README.md）
└── start.py
```

---

## 七、离线评估（RAGAS 风格）

`eval/` 目录提供一套基于 LLM-as-Judge 的离线评估脚本：

```bash
uv run python eval/run_eval.py --questions eval/sample_questions.json
```

**评估三个核心指标**：

- **Context Precision** — 检索到的 Top-K chunk 与问题的相关比例（按 rank 加权）
- **Faithfulness** — 答案中的 claim 是否都能从 context 推出（防幻觉）
- **Answer Relevancy** — 答案是否真的回答了问题

结果落盘 `eval/results/eval-{timestamp}.json`，可用于回归对比 / 改动验证。

### 当前评估结果（2026-05-28 baseline）

在 10 道针对当前语料（React 组件库/Hook 教程，751 chunks / 18 docs）的人工设计问题上（基线模型配置：qwen-turbo + gte-rerank，完整参数见结果 JSON 的 config 段）：

| 指标 | 分数 | 解读 |
|---|---|---|
| Context Precision | **0.858** | 检索阶段 Top-3 chunk 平均 ~86% 与问题相关 |
| Faithfulness | **0.867** | 生成答案 ~87% 的 claim 能从 context 推出，**显著降低幻觉** |
| Answer Relevancy | **0.847** | 答案与原问题语义对齐度 0.85（embedding 余弦） |

> 完整结果见 [`eval/results/`](eval/results/) 下最新 JSON。这是项目支持"幻觉问题解决，回答准确度优于原生 LLM"这一结论的量化依据。详见 [eval/README.md](eval/README.md)。

### 消融实验（2026-07）

用 `eval/run_ablation.py` 对混合检索 / 精排做 2×2 全组合对照（35 题 · 裁判模型 qwen-turbo · 生成模型 qwen3.7-plus）。口径说明：**"无精排"同时关闭相关性阈值**（阈值只作用于 0..1 精排分）。

| 配置 | Context Precision | Faithfulness | Answer Relevancy |
|---|---|---|---|
| 混检 + 精排（基线） | 0.943 | 0.906 | 0.793 |
| 混检，无精排 | 0.850 (-0.093) | 0.797 (-0.109) | 0.748 (-0.045) |
| 纯向量 + 精排 | 0.948 (+0.005) | 0.927 (+0.021) | 0.840 (+0.047) |
| 纯向量，无精排 | 0.852 (-0.090) | 0.846 (-0.060) | 0.787 (-0.006) |

分题型 Context Precision：

| 配置 | factual | paraphrase | proper_noun |
|---|---|---|---|
| 混检 + 精排（基线） | 0.949 (n=13) | 0.948 (n=8) | 0.935 (n=14) |
| 混检，无精排 | 0.776 (n=13) | 0.812 (n=8) | 0.940 (n=14) |
| 纯向量 + 精排 | 0.962 (n=13) | 0.948 (n=8) | 0.935 (n=14) |
| 纯向量，无精排 | 0.788 (n=13) | 0.865 (n=8) | 0.905 (n=14) |

结论：精排（+阈值）是质量的最大单一贡献者；在本语料规模下混检的净收益有限——full 配置 105 个最终 chunk 中 78 个双路命中、22 个纯向量独供、仅 5 个（4.8%）由 BM25 独供，小语料上稠密召回 Top-20 已近全覆盖。混检的专有名词优势只在无精排管线中显现（no-rerank 时 proper_noun 类 CP 0.940 vs 0.905）。保留混检的工程理由：语料增长后稠密召回覆盖会被稀释，BM25 是低成本的召回保险，且实验证明精排能把混检引入的噪声清理干净。完整数据见 [`eval/results/ablation-20260726-215512/summary.md`](eval/results/ablation-20260726-215512/summary.md)。

---

## 八、关键实现位置（追问时直接定位）

| 关注点 | 位置 |
|---|---|
| Retriever 主流程 | [app/services/retriever.py:192](app/services/retriever.py) `Retriever.search` |
| RRF 实现 | [app/services/retriever.py:149](app/services/retriever.py) `_rrf_fuse` |
| FAISS 向量召回 | [app/services/retriever.py:116](app/services/retriever.py) `_vector_search` |
| BM25 (jieba) 召回 | [app/services/retriever.py:134](app/services/retriever.py) `_bm25_search` |
| gte-rerank 调用 | [app/services/retriever.py:163](app/services/retriever.py) `_rerank` |
| 切片策略 | [app/services/doc_service.py](app/services/doc_service.py) `_make_chunks` |
| 流式问答 | [app/api/chat.py](app/api/chat.py) `chat_stream` |
| 多格式解析 | [app/utils/doc_parser.py](app/utils/doc_parser.py) `parse_pages` |

---

## 九、已知限制 / TODO

- [ ] FAISS 当前用 `IndexFlatL2`（暴力搜索），文档量超过 10k 后需切到 `IndexHNSWFlat`
- [ ] Metadata filter 当前只挂在 chunk 上做溯源展示，检索阶段未传 filter（切 Qdrant 后可启用）
- [ ] 多用户隔离未实现（共享单库）
- [ ] 流式中断后已渲染的 token buffer 未清理（前端 store 改进点）
- [ ] eval 数据集当前 10 道（CP=0.858, FA=0.867, AR=0.847），后续扩到 100+ 提升统计意义

---

## 十、技术栈版本

- Python 3.12 / FastAPI / LangChain Community
- DashScope SDK（embedding + rerank + LLM 三件套）
- FAISS-CPU
- rank_bm25 + jieba（中文 BM25）
- Vue 3.5 + TS + Vite 7 + Element Plus 2.13 + Pinia 3 + Tailwind 4（前端）
