import json
import logging
from typing import Generator

import requests

from app.core.config import get_settings
from app.services import doc_service
from app.services.retriever import get_retriever

settings = get_settings()
logger = logging.getLogger(__name__)

# OpenAI-compatible endpoint supports all Qwen models (qwen3.7-plus, qwen-plus, etc.)
COMPATIBLE_API = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def _ndjson(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


class ChatService:
    @staticmethod
    def chat_stream(question: str, top_k: int = 3) -> Generator[str, None, None]:
        """Stream JSON-Lines events for a single RAG turn.

        Event shape:
          {"step": "init"|"retrieving"|"retrieved"|"reranking"|"generating"
                  |"answer"|"completed"|"error",
           "message": str?, "data": any?, "done": bool?}
        """
        yield _ndjson({"step": "init", "message": "正在初始化问答服务..."})

        try:
            if not settings.DASHSCOPE_API_KEY:
                yield _ndjson({"step": "error", "message": "未配置 API Key", "done": True})
                return

            # Chunks corpus is the source of truth for the new retriever. An
            # empty corpus with non-empty metadata means legacy data needs a
            # one-time rebuild (e.g. after upgrading to this version).
            if not doc_service.CHUNKS_CORPUS:
                indexed_docs = [
                    d for d in doc_service.DOCS_METADATA if d.get("status") == "已索引"
                ]
                if not indexed_docs:
                    yield _ndjson(
                        {"step": "error", "message": "知识库为空，请先上传文档", "done": True}
                    )
                    return
                yield _ndjson(
                    {
                        "step": "retrieving",
                        "message": "检测到知识库为空但存在已索引文档，正在重建...",
                    }
                )
                try:
                    doc_service.DocService.rebuild_index()
                except Exception as e:
                    yield _ndjson(
                        {"step": "error", "message": f"重建索引异常: {e}", "done": True}
                    )
                    return
                if not doc_service.CHUNKS_CORPUS:
                    yield _ndjson(
                        {
                            "step": "error",
                            "message": "知识库重建失败，请重新上传文档",
                            "done": True,
                        }
                    )
                    return

            yield _ndjson(
                {"step": "retrieving", "message": f"正在检索相关文档 (Top {top_k})..."}
            )

            retriever = get_retriever()
            if settings.ENABLE_RERANK:
                # Surface rerank as its own step so the UI can show the pipeline.
                yield _ndjson(
                    {"step": "reranking", "message": "正在使用 rerank 模型精排候选片段..."}
                )
            hits = retriever.search(question, top_k=top_k)

            sources = [
                {
                    "content": h.text[:200] + ("..." if len(h.text) > 200 else ""),
                    "score": round(h.score, 4),
                    "source": h.doc_name,
                    "page": h.page,
                    "doc_id": h.doc_id,
                    "methods": h.methods,
                    "vector_rank": h.vector_rank,
                    "bm25_rank": h.bm25_rank,
                }
                for h in hits
            ]
            yield _ndjson(
                {
                    "step": "retrieved",
                    "data": sources,
                    "message": f"检索到 {len(hits)} 个相关片段",
                }
            )

            if not hits:
                yield _ndjson(
                    {
                        "step": "answer",
                        "data": (
                            "很抱歉，在现有知识库中未找到与您问题相关的答案。建议您：\n"
                            "1. 尝试更换关键词\n"
                            "2. 确认已上传相关文档\n"
                            "3. 检查问题描述是否准确"
                        ),
                        "done": False,
                    }
                )
                yield _ndjson({"step": "completed", "message": "回答完成", "done": True})
                return

            yield _ndjson({"step": "generating", "message": "正在生成回答..."})

            # Cite chunks by index so the model can reference [1][2][3] if it chooses.
            context_blocks = [
                f"【片段 {i + 1} - 来源: {h.doc_name} - 第 {h.page} 页】\n{h.text}"
                for i, h in enumerate(hits)
            ]
            context = "\n\n".join(context_blocks)
            prompt = (
                "请基于以下参考内容回答用户的问题。如果参考内容不足以回答，请委婉告知用户"
                "并说明原因；不要编造事实。引用具体信息时可以用 [片段编号] 标注来源。\n\n"
                f"参考内容：\n{context}\n\n用户问题：{question}"
            )

            api_response = requests.post(
                COMPATIBLE_API,
                headers={
                    "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
                stream=True,
                timeout=120,
            )

            if api_response.status_code != 200:
                error_msg = api_response.json().get("message", api_response.text)
                yield _ndjson({"step": "error", "message": f"模型调用失败: {error_msg}"})
                yield _ndjson({"step": "completed", "message": "回答完成", "done": True})
                return

            for line in api_response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"]
                        if "content" in delta:
                            yield _ndjson({"step": "answer", "data": delta["content"], "done": False})
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

            yield _ndjson({"step": "completed", "message": "回答完成", "done": True})

        except Exception as e:
            logger.exception("Chat error")
            yield _ndjson({"step": "error", "message": f"系统异常: {e}", "done": True})
