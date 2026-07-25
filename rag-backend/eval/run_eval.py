"""RAGAS-style offline evaluation for the local RAG system.

Computes three metrics via LLM-as-Judge (qwen-turbo) on a sample question set:
  * Context Precision   — relevance of retrieved chunks, rank-weighted
  * Faithfulness        — fraction of answer claims grounded in context
  * Answer Relevancy    — cosine similarity between original query and N queries
                          re-generated from the answer (high = answer addresses
                          the actual question)

The script is self-contained: it imports the project's Retriever + DashScope
embeddings + qwen LLM directly, no external `ragas` lib required.

Usage:
    uv run python eval/run_eval.py --questions eval/sample_questions.json

The script must be run from the rag-backend/ directory so relative imports work.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Make sure we can import the app from anywhere we are launched.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import requests
from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import get_settings
from app.services.retriever import RetrievalHit, get_retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("rag-eval")


# --------------------------------------------------------------------------- #
# LLM call wrappers                                                            #
# --------------------------------------------------------------------------- #

def _llm(prompt: str, *, temperature: float = 0.1, max_tokens: int = 512) -> str:
    s = get_settings()
    resp = requests.post(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {s.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": s.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        msg = resp.json().get("message", resp.text)
        raise RuntimeError(f"LLM call failed: {msg}")
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _embed(texts: list[str]) -> np.ndarray:
    s = get_settings()
    emb = DashScopeEmbeddings(model=s.EMBEDDING_MODEL, dashscope_api_key=s.DASHSCOPE_API_KEY)
    vectors = emb.embed_documents(texts)
    return np.array(vectors, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# --------------------------------------------------------------------------- #
# Generation: ask the system, get an answer (mirrors chat_service prompt)     #
# --------------------------------------------------------------------------- #

ANSWER_PROMPT = """你是一个严谨的知识库问答助手。请仅基于下方"参考资料"回答问题。
如果资料中没有答案，请明确回答"根据提供的资料无法回答该问题"，不要编造。

参考资料：
{context}

问题：{question}

要求：
1. 答案要简洁明了，不要超过 200 字。
2. 只使用资料中的信息，不要引入外部知识。
3. 如有引用，标注 [chunk_N] 编号。

答案："""


def generate_answer(question: str, chunks: list[RetrievalHit]) -> str:
    if not chunks:
        return "根据提供的资料无法回答该问题"
    context_parts = []
    for i, c in enumerate(chunks, start=1):
        context_parts.append(f"[chunk_{i}] (来源: {c.doc_name}, 第{c.page}页)\n{c.text}")
    context = "\n\n".join(context_parts)
    return _llm(ANSWER_PROMPT.format(context=context, question=question), temperature=0.2)


# --------------------------------------------------------------------------- #
# Metric 1: Context Precision                                                  #
# --------------------------------------------------------------------------- #

CTX_PRECISION_PROMPT = """判断下面这段"参考资料"对回答给定"问题"是否有用。

问题：{question}

参考资料：
{chunk}

只输出一个数字：1 表示有用，0 表示无用。不要任何其他文字。"""


def judge_chunk_relevant(question: str, chunk_text: str) -> int:
    out = _llm(CTX_PRECISION_PROMPT.format(question=question, chunk=chunk_text), temperature=0.0, max_tokens=4)
    m = re.search(r"[01]", out)
    return int(m.group(0)) if m else 0


def context_precision(question: str, chunks: list[RetrievalHit]) -> float:
    """RAGAS-style rank-weighted precision.

    precision@k = (relevant in top-k) / k
    CP = Σ (precision@k × is_relevant_k) / total_relevant
    """
    if not chunks:
        return 0.0
    relevances = [judge_chunk_relevant(question, c.text) for c in chunks]
    total_relevant = sum(relevances)
    if total_relevant == 0:
        return 0.0
    score = 0.0
    for k in range(1, len(chunks) + 1):
        if relevances[k - 1] == 1:
            precision_at_k = sum(relevances[:k]) / k
            score += precision_at_k
    return score / total_relevant


# --------------------------------------------------------------------------- #
# Metric 2: Faithfulness                                                       #
# --------------------------------------------------------------------------- #

STATEMENT_SPLIT_PROMPT = """把下面这段答案拆分成独立的事实性陈述（每行一条，不要编号，不要解释）。
事实性陈述指的是可以被验证为对或错的陈述句。如果某些内容是修辞、连接词或者重复，不要算作独立陈述。

答案：
{answer}

输出（每行一条）："""

FAITHFULNESS_JUDGE_PROMPT = """根据"参考资料"，判断下面"陈述"是否完全成立。
完全成立指的是该陈述的信息能从参考资料中直接推出，且没有与之矛盾的内容。

参考资料：
{context}

陈述：{statement}

只输出一个数字：1 表示成立，0 表示不成立。不要其他文字。"""


def split_statements(answer: str) -> list[str]:
    if not answer or "无法回答" in answer:
        return []
    out = _llm(STATEMENT_SPLIT_PROMPT.format(answer=answer), temperature=0.0, max_tokens=400)
    lines = [ln.strip(" -•·.0123456789、 ").strip() for ln in out.split("\n")]
    return [ln for ln in lines if len(ln) > 5]


def faithfulness(answer: str, chunks: list[RetrievalHit]) -> float:
    statements = split_statements(answer)
    if not statements:
        return 0.0
    context = "\n\n".join(c.text for c in chunks)
    judgements = []
    for st in statements:
        out = _llm(
            FAITHFULNESS_JUDGE_PROMPT.format(context=context, statement=st),
            temperature=0.0,
            max_tokens=4,
        )
        m = re.search(r"[01]", out)
        judgements.append(int(m.group(0)) if m else 0)
    return sum(judgements) / len(judgements)


# --------------------------------------------------------------------------- #
# Metric 3: Answer Relevancy                                                   #
# --------------------------------------------------------------------------- #

REVERSE_QUERY_PROMPT = """根据下面这段"答案"，反向生成 {n} 个可能引出这段答案的"问题"。
每行一个问题，不要编号，不要解释，简洁。

答案：
{answer}

问题："""


def answer_relevancy(question: str, answer: str, n_queries: int = 3) -> float:
    if not answer or "无法回答" in answer:
        return 0.0
    out = _llm(
        REVERSE_QUERY_PROMPT.format(answer=answer, n=n_queries),
        temperature=0.7,
        max_tokens=300,
    )
    lines = [ln.strip(" -•·.0123456789、 ?？").strip() for ln in out.split("\n")]
    candidates = [ln for ln in lines if len(ln) > 3][:n_queries]
    if not candidates:
        return 0.0
    vectors = _embed([question] + candidates)
    q_vec = vectors[0]
    sims = [_cosine(q_vec, vectors[i]) for i in range(1, len(vectors))]
    return float(np.mean(sims))


# --------------------------------------------------------------------------- #
# Result dataclasses                                                           #
# --------------------------------------------------------------------------- #

@dataclass
class PerQuestionResult:
    id: str
    question: str
    answer: str
    retrieved_chunks: list[dict] = field(default_factory=list)
    context_precision: float = 0.0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    error: Optional[str] = None


@dataclass
class Summary:
    num_questions: int
    context_precision: float
    faithfulness: float
    answer_relevancy: float
    duration_seconds: float


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def run(questions_path: Path, top_k: int, n_relevancy: int, limit: Optional[int]) -> tuple[Summary, list[PerQuestionResult]]:
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    if limit:
        questions = questions[:limit]

    retriever = get_retriever()
    results: list[PerQuestionResult] = []
    started = time.time()

    for idx, q in enumerate(questions, start=1):
        qid = q.get("id") or f"Q{idx:03d}"
        question = q["question"]
        log.info("[%d/%d] %s — %s", idx, len(questions), qid, question)

        try:
            hits = retriever.search(question, top_k=top_k)
            answer = generate_answer(question, hits)
            cp = context_precision(question, hits) if hits else 0.0
            fa = faithfulness(answer, hits) if hits else 0.0
            ar = answer_relevancy(question, answer, n_queries=n_relevancy)
            log.info("    CP=%.2f  FA=%.2f  AR=%.2f", cp, fa, ar)
            results.append(PerQuestionResult(
                id=qid,
                question=question,
                answer=answer,
                retrieved_chunks=[{
                    "chunk_id": h.chunk_id,
                    "doc_name": h.doc_name,
                    "page": h.page,
                    "score": h.score,
                    "methods": h.methods,
                    "text_preview": h.text[:120],
                } for h in hits],
                context_precision=cp,
                faithfulness=fa,
                answer_relevancy=ar,
            ))
        except Exception as e:
            log.error("    failed: %s", e)
            results.append(PerQuestionResult(
                id=qid, question=question, answer="", error=str(e),
            ))

    valid = [r for r in results if r.error is None]
    n = len(valid) if valid else 1
    summary = Summary(
        num_questions=len(results),
        context_precision=sum(r.context_precision for r in valid) / n,
        faithfulness=sum(r.faithfulness for r in valid) / n,
        answer_relevancy=sum(r.answer_relevancy for r in valid) / n,
        duration_seconds=time.time() - started,
    )
    return summary, results


def main() -> int:
    ap = argparse.ArgumentParser(description="RAGAS-style offline eval (LLM-as-Judge)")
    ap.add_argument("--questions", type=Path, default=Path("eval/sample_questions.json"))
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--num-relevancy-queries", type=int, default=3)
    ap.add_argument("--output", type=Path, default=Path("eval/results/"))
    ap.add_argument("--limit", type=int, default=None, help="Only evaluate first N questions")
    args = ap.parse_args()

    if not args.questions.exists():
        log.error("Questions file not found: %s", args.questions)
        return 2

    settings = get_settings()
    if not settings.DASHSCOPE_API_KEY:
        log.error("DASHSCOPE_API_KEY not set. Configure .env first.")
        return 2

    summary, results = run(args.questions, args.top_k, args.num_relevancy_queries, args.limit)

    args.output.mkdir(parents=True, exist_ok=True)
    out_path = args.output / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": asdict(summary),
            "config": {
                "top_k": args.top_k,
                "num_relevancy_queries": args.num_relevancy_queries,
                "embedding_model": settings.EMBEDDING_MODEL,
                "llm_model": settings.LLM_MODEL,
                "rerank_model": settings.RERANK_MODEL,
                "rrf_k": settings.RRF_K,
                "relevance_threshold": settings.RELEVANCE_THRESHOLD,
            },
            "per_question": [asdict(r) for r in results],
        }, f, ensure_ascii=False, indent=2)

    log.info("=" * 60)
    log.info("Summary: N=%d  CP=%.3f  FA=%.3f  AR=%.3f  (%.1fs)",
             summary.num_questions, summary.context_precision,
             summary.faithfulness, summary.answer_relevancy,
             summary.duration_seconds)
    log.info("Result written: %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
