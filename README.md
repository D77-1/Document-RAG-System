# Document-RAG-System

**本地知识库混合检索问答系统** · FastAPI + LangChain + FAISS + Vue 3

把 PDF / Word / Markdown / TXT 变成可追问的知识库：两阶段混合检索（FAISS 稠密召回 + BM25 稀疏召回 → RRF 融合 → Cross-Encoder 精排），检索不到就明确拒答，回答质量用离线评估量化跟踪。

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white)
![Vue 3](https://img.shields.io/badge/Vue_3-4FC08D?logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 这个 RAG 和"调一次 API 的 demo"差在哪

**1. 检索是两阶段混合，不是单路向量。**
中文场景里的专有名词、缩写、短查询，纯向量召回容易漏。这里 FAISS 稠密与 BM25（jieba 分词）稀疏双路并行召回，用 RRF（k=60）做排名融合——只用 rank 不用分数，天然免疫两路分数尺度不可比的问题——再经 cross-encoder 精排，低于 0.2 相关性阈值的片段直接丢弃：**宁可拒答，不喂低相关上下文给模型编故事。**

**2. 效果有数字，不靠"感觉变好了"。**
自建 RAGAS 风格 LLM-as-Judge 离线评估（[rag-backend/eval/](rag-backend/eval/)），三个指标可复现、可回归：

| 指标 | 分数 | 含义 |
|---|---|---|
| Context Precision | **0.858** | 检索出的 Top-3 片段中相关片段占比（按排名加权） |
| Faithfulness | **0.867** | 答案中的事实陈述能从检索内容推出的比例（防幻觉） |
| Answer Relevancy | **0.847** | 答案与原问题的语义对齐度 |

> 2026-05 基线：18 文档 / 751 chunks / 10 题；评测时模型为 qwen-turbo + gte-rerank（完整配置随结果落盘于 [eval/results/](rag-backend/eval/results/)）。评测集扩充与检索消融实验见 [Roadmap](#roadmap)。

**3. 过程全透明。**
NDJSON 全链路流式：检索 → 精排 → 生成逐步推送，前端把每一步画出来；每条回答附来源片段、页码与命中路径（vector / bm25 / 双路命中）。

## 架构

```
【索引链路】
  上传 → 解析 (PDF/DOCX/MD/TXT) → Markdown 结构化切片 (500/50) → text-embedding-v3 → FAISS 落盘

【问答链路】
           ┌─► FAISS 稠密召回 (Top 20) ─┐
  提问 ────┤                            ├─► RRF 融合 (k=60) ─► Cross-Encoder 精排
           └─► BM25 稀疏召回 (Top 20) ─┘
       ─► 阈值过滤 (≥0.2) ─► Top-3 上下文 ─► qwen 流式生成 ─► NDJSON ─► 前端逐 token 渲染
```

<!-- TODO(截图): 系统跑起来后截两张图放到 docs/screenshots/ 目录，然后取消下面的注释
## 界面预览

| 智能问答（检索过程与来源可视化） | 文档管理（在线预览） |
|---|---|
| ![Chat](docs/screenshots/chat.png) | ![Docs](docs/screenshots/docs.png) |
-->

## 快速开始

前置：Python 3.12+ · Node.js 18+ · [阿里云 DashScope API Key](https://dashscope.console.aliyun.com/)

```bash
# 1. 后端 (rag-backend/)
cp .env.example .env         # 填入 DASHSCOPE_API_KEY
uv sync
uv run start.py              # http://localhost:8000 ，Swagger 见 /docs

# 2. 前端 (rag-frontend/) —— Vite 已代理 /api → 8000，请先启动后端
npm install
npm run dev                  # http://localhost:5173
```

## 项目结构

```
├── rag-backend/     # FastAPI + LangChain：解析、切片、索引、混合检索、流式问答、离线评估
└── rag-frontend/    # Vue 3 + TS + Pinia：问答界面（过程可视化）、文档管理与在线预览
```

## 深入文档

- **[后端架构与技术决策表](rag-backend/README.md)** —— 每个选型的 "Why this, not that"：RRF vs 加权融合、FlatL2 vs HNSW、阈值取舍、切片策略等
- **[评估方法与指标定义](rag-backend/eval/README.md)** —— LLM-as-Judge 三指标的计算方式与局限

## Roadmap

- [ ] 检索消融实验：混检 / 精排 2×2 对照，评测集 10 → 35+
- [ ] 多轮对话与查询改写（指代消解）
- [ ] Docker Compose 一键部署 + 线上 Demo
- [ ] 文档量上万后：FAISS `IndexFlatL2` → `IndexHNSWFlat`，metadata filter 下推到检索层

## License

[MIT](LICENSE)
