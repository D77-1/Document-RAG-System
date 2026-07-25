# RAG 离线评估（RAGAS 风格 · LLM-as-Judge）

> 目标：用可重复的脚本量化「检索质量 + 生成忠实度 + 答案相关性」，为简历/PR 中
> 「显著降低幻觉、回答优于原生 LLM」的结论提供数据支撑。

---

## 评估指标

参考 RAGAS 框架的三个核心指标，全部用 LLM-as-Judge（qwen-turbo）打分：

| 指标 | 含义 | 算法 |
|---|---|---|
| **Context Precision** | 检索到的 Top-K chunk 中相关的比例（按 rank 加权）| LLM 逐 chunk 判断「这个 chunk 对回答 query 有用吗」(0/1) → 计算加权平均：`Σ (precision@k × is_relevant_k) / num_relevant` |
| **Faithfulness** | 答案中的 claim 是否都能从 context 推出（防幻觉）| LLM 把 answer 拆 statements → 逐条判断是否被 context 支持 → `supported / total` |
| **Answer Relevancy** | 答案是否真的回答了问题（避免答非所问）| LLM 基于 answer 反向生成 N 个 query → 与原 query 算 embedding 余弦相似度 → 取均值 |

---

## 文件说明

```
eval/
├── README.md              # 本文件
├── run_eval.py            # 主入口
├── sample_questions.json  # 题库（question + ground_truth_keywords）
└── results/               # 每次跑分的结果 JSON（gitignore）
```

---

## 用法

### 1. 准备题库

`sample_questions.json` 是一个 list，每条至少包含：

```json
[
  {
    "id": "Q001",
    "question": "RAG 系统中为什么要做 rerank？",
    "ground_truth_keywords": ["bi-encoder", "cross-encoder", "精度", "两阶段"]
  }
]
```

- `ground_truth_keywords`：可选，用于辅助校验答案是否命中关键词。
- 建议规模 20-100 题，覆盖：精确召回（专有名词）/ 长尾查询 / 多跳推理 / 边界 case（语料里没有的问题，验证模型会不会编）。

### 2. 跑评估

```bash
# 在 rag-backend/ 目录下
uv run python eval/run_eval.py \
  --questions eval/sample_questions.json \
  --top-k 3 \
  --num-relevancy-queries 3 \
  --output eval/results/
```

参数说明：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--questions` | `eval/sample_questions.json` | 题库路径 |
| `--top-k` | `3` | 检索返回的 chunk 数 |
| `--num-relevancy-queries` | `3` | Answer Relevancy 时反向生成几个 query 取均值 |
| `--output` | `eval/results/` | 结果落盘目录 |
| `--limit` | 不限 | 只评估前 N 题（调试用）|

### 3. 看结果

每次运行产出 `eval/results/eval-{YYYYMMDD-HHMMSS}.json`：

```json
{
  "summary": {
    "num_questions": 20,
    "context_precision": 0.78,
    "faithfulness": 0.92,
    "answer_relevancy": 0.85,
    "duration_seconds": 142.3
  },
  "per_question": [
    {
      "id": "Q001",
      "question": "...",
      "answer": "...",
      "retrieved_chunks": [...],
      "context_precision": 1.0,
      "faithfulness": 0.83,
      "answer_relevancy": 0.91
    }
  ]
}
```

### 4. 解读

- **Faithfulness < 0.8** → 模型在编内容，需要检查 prompt（是否强约束 grounded）
- **Context Precision < 0.6** → 检索阶段有问题（rerank 阈值太低？候选数太少？）
- **Answer Relevancy < 0.7** → 答案跑题，prompt 模板的 instruction 不够明确

---

## 注意事项

- LLM-as-Judge **本身有方差**：同一条 case 跑 3 次评分可能差 0.1。建议同 batch 多次跑取均值。
- 评估本身要花 token：每题 ≈ `top_k × 1` (context_precision) + `1` (faithfulness 拆 + 判) + `num_relevancy_queries` (relevancy 反向生成)。20 题大约 60-100 次 LLM 调用。
- 避免用同一个 LLM 既生成又评估同一道题——会偏乐观。理想做法是评估时换更强的模型（如 qwen-max）。
