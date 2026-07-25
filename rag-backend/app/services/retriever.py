"""Hybrid retriever: dense (FAISS) + sparse (BM25) → RRF fusion → optional rerank.

Design goals:
  * Each query independently asks both FAISS and BM25 for candidates.
  * Reciprocal Rank Fusion (RRF) combines the two rank lists in a way that
    doesn't require score normalization across heterogeneous scorers.
  * An optional cross-encoder rerank (DashScope gte-rerank) is applied to the
    fused candidates; its score is the final 0..1 relevance used for filtering.
  * The corpus that BM25 indexes is the same chunks_corpus.json that
    doc_service maintains, so add/delete in doc_service is reflected here on
    the next search via a length-based staleness check.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import jieba
from rank_bm25 import BM25Okapi

from dashscope import TextReRank
from http import HTTPStatus

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS

from app.core.config import get_settings
from app.services import doc_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievalHit:
    chunk_id: str
    text: str
    doc_name: str
    page: int
    doc_id: Optional[str]
    score: float                # final score (rerank if available, else fused)
    methods: list[str]          # which retrievers contributed: ["vector"], ["bm25"], or both
    vector_rank: Optional[int] = None
    bm25_rank: Optional[int] = None


def _tokenize(text: str) -> list[str]:
    """jieba handles CJK; ascii words pass through. Lowercased for case-insensitive BM25."""
    return [tok.strip().lower() for tok in jieba.lcut(text) if tok.strip()]


# Warm up jieba so first query isn't slow.
jieba.initialize()


class Retriever:
    def __init__(self):
        self.settings = get_settings()
        self._embeddings: Optional[DashScopeEmbeddings] = None
        self._vector_store: Optional[FAISS] = None
        self._vector_store_mtime: float = 0.0

        self._bm25: Optional[BM25Okapi] = None
        self._bm25_ids: list[str] = []
        self._bm25_corpus_size: int = -1

    # ---- lazy resources ----

    def _get_embeddings(self) -> Optional[DashScopeEmbeddings]:
        if self._embeddings is None and self.settings.DASHSCOPE_API_KEY:
            self._embeddings = DashScopeEmbeddings(
                model=self.settings.EMBEDDING_MODEL,
                dashscope_api_key=self.settings.DASHSCOPE_API_KEY,
            )
        return self._embeddings

    def _get_vector_store(self) -> Optional[FAISS]:
        index_file = os.path.join(self.settings.VECTOR_DB_DIR, "index.faiss")
        if not os.path.exists(index_file):
            return None
        # Reload if the on-disk index changed (covers uploads/deletes between queries).
        mtime = os.path.getmtime(index_file)
        if self._vector_store is None or mtime != self._vector_store_mtime:
            emb = self._get_embeddings()
            if emb is None:
                return None
            try:
                self._vector_store = FAISS.load_local(
                    self.settings.VECTOR_DB_DIR,
                    emb,
                    allow_dangerous_deserialization=True,
                )
                self._vector_store_mtime = mtime
            except Exception as e:
                logger.error(f"Failed to load FAISS: {e}")
                return None
        return self._vector_store

    def _get_bm25(self) -> tuple[Optional[BM25Okapi], list[str]]:
        corpus = doc_service.CHUNKS_CORPUS
        if not corpus:
            return None, []
        # Rebuild if the corpus size changed since last build.
        if self._bm25 is None or len(corpus) != self._bm25_corpus_size:
            ids = list(corpus.keys())
            tokenized = [_tokenize(corpus[cid]["text"]) for cid in ids]
            self._bm25 = BM25Okapi(tokenized)
            self._bm25_ids = ids
            self._bm25_corpus_size = len(corpus)
        return self._bm25, self._bm25_ids

    # ---- search primitives ----

    def _vector_search(self, query: str, k: int) -> list[tuple[str, float]]:
        vs = self._get_vector_store()
        if vs is None:
            return []
        try:
            results = vs.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
        hits: list[tuple[str, float]] = []
        for doc, score in results:
            cid = doc.metadata.get("chunk_id")
            if cid is None:
                # Legacy chunk pre-metadata-injection; skip.
                continue
            hits.append((cid, float(score)))
        return hits

    def _bm25_search(self, query: str, k: int) -> list[tuple[str, float]]:
        bm25, ids = self._get_bm25()
        if bm25 is None or not ids:
            return []
        try:
            scores = bm25.get_scores(_tokenize(query))
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
        ranked = sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)
        # Drop zero-scored entries (no token overlap is uninformative).
        return [(cid, float(s)) for cid, s in ranked[:k] if s > 0]

    # ---- fusion + rerank ----

    @staticmethod
    def _rrf_fuse(
        rankings: list[list[tuple[str, float]]], k: int
    ) -> list[tuple[str, float, set[int]]]:
        """Reciprocal Rank Fusion. Returns [(chunk_id, fused_score, set_of_source_ranks)]."""
        fused: dict[str, float] = {}
        contributors: dict[str, set[int]] = {}
        for source_idx, ranking in enumerate(rankings):
            for rank, (cid, _score) in enumerate(ranking):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank + 1)
                contributors.setdefault(cid, set()).add(source_idx)
        ordered = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        return [(cid, score, contributors[cid]) for cid, score in ordered]

    def _rerank(self, query: str, candidates: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return list of (original_index, relevance_score) sorted desc by score."""
        if not candidates or not self.settings.DASHSCOPE_API_KEY:
            return []
        try:
            resp = TextReRank.call(
                model=self.settings.RERANK_MODEL,
                query=query,
                documents=candidates,
                top_n=top_n,
                return_documents=False,
                api_key=self.settings.DASHSCOPE_API_KEY,
            )
        except Exception as e:
            logger.error(f"Rerank call failed: {e}")
            return []
        if resp.status_code != HTTPStatus.OK:
            logger.error(f"Rerank failed: {resp.message}")
            return []
        results = getattr(resp.output, "results", None) or []
        out: list[tuple[int, float]] = []
        for r in results:
            idx = r.get("index") if isinstance(r, dict) else r.index
            score = r.get("relevance_score") if isinstance(r, dict) else r.relevance_score
            out.append((int(idx), float(score)))
        return out

    # ---- public API ----

    def search(self, query: str, top_k: Optional[int] = None) -> list[RetrievalHit]:
        s = self.settings
        top_k = top_k or s.TOP_K

        vector_hits = self._vector_search(query, s.VECTOR_CANDIDATES)
        bm25_hits = self._bm25_search(query, s.BM25_CANDIDATES) if s.ENABLE_HYBRID else []

        rankings: list[list[tuple[str, float]]] = []
        if vector_hits:
            rankings.append(vector_hits)
        if bm25_hits:
            rankings.append(bm25_hits)
        if not rankings:
            return []

        fused = self._rrf_fuse(rankings, s.RRF_K)
        # Cap candidates fed to rerank to keep API payload bounded.
        candidate_cap = max(top_k * 5, s.VECTOR_CANDIDATES)
        fused = fused[:candidate_cap]

        vector_id_to_rank = {cid: i + 1 for i, (cid, _) in enumerate(vector_hits)}
        bm25_id_to_rank = {cid: i + 1 for i, (cid, _) in enumerate(bm25_hits)}

        corpus = doc_service.CHUNKS_CORPUS
        # Map fused candidates back to chunk metadata; drop any that vanished from corpus.
        cand_ids: list[str] = []
        cand_meta: list[dict] = []
        fused_scores: dict[str, float] = {}
        contributor_sources: dict[str, set[int]] = {}
        for cid, fscore, sources in fused:
            entry = corpus.get(cid)
            if entry is None:
                continue
            cand_ids.append(cid)
            cand_meta.append(entry)
            fused_scores[cid] = fscore
            contributor_sources[cid] = sources

        if not cand_ids:
            return []

        # Rerank if enabled; otherwise the fused order is final.
        # Track whether rerank *actually* produced scores so we only apply the
        # relevance threshold to genuine 0..1 rerank scores (not to RRF scores).
        rerank_applied = False
        final_order: list[tuple[str, dict, float]] = []
        if s.ENABLE_RERANK and s.DASHSCOPE_API_KEY:
            texts = [m["text"] for m in cand_meta]
            reranked = self._rerank(query, texts, top_n=top_k)
            if reranked:
                rerank_applied = True
                for idx, score in reranked:
                    if 0 <= idx < len(cand_ids):
                        final_order.append((cand_ids[idx], cand_meta[idx], score))
            else:
                # Rerank failed — fall back to fused order with fused scores
                for cid, meta in list(zip(cand_ids, cand_meta))[:top_k]:
                    final_order.append((cid, meta, fused_scores[cid]))
        else:
            for cid, meta in list(zip(cand_ids, cand_meta))[:top_k]:
                final_order.append((cid, meta, fused_scores[cid]))

        # Apply relevance threshold only when rerank *actually* produced 0..1
        # scores.  RRF fused scores are rank-based and not on a 0..1 scale.
        threshold = s.RELEVANCE_THRESHOLD if rerank_applied else 0.0
        results: list[RetrievalHit] = []
        for cid, meta, score in final_order:
            if score < threshold:
                continue
            methods: list[str] = []
            sources = contributor_sources.get(cid, set())
            # source index 0 was vector (if it ran), 1 was bm25
            method_order = []
            if vector_hits:
                method_order.append("vector")
            if bm25_hits:
                method_order.append("bm25")
            for i, name in enumerate(method_order):
                if i in sources:
                    methods.append(name)
            results.append(
                RetrievalHit(
                    chunk_id=cid,
                    text=meta["text"],
                    doc_name=meta.get("doc_name") or "未知文档",
                    page=int(meta.get("page") or 1),
                    doc_id=meta.get("doc_id"),
                    score=score,
                    methods=methods,
                    vector_rank=vector_id_to_rank.get(cid),
                    bm25_rank=bm25_id_to_rank.get(cid),
                )
            )
        return results


_retriever_singleton: Optional[Retriever] = None


def get_retriever() -> Retriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = Retriever()
    return _retriever_singleton
