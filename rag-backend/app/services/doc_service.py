import os
import uuid
import shutil
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException, BackgroundTasks
from app.core.config import get_settings
from app.utils.doc_parser import DocParser
from app.schemas.doc import UploadResponse, DocItem, DocListResponse
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

settings = get_settings()
logger = logging.getLogger(__name__)

METADATA_FILE = os.path.join(settings.UPLOAD_DIR, "metadata.json")
# Chunk corpus: source-of-truth for BM25 and targeted delete.
# Kept outside UPLOAD_DIR so file scans don't trip over it.
CORPUS_FILE = os.path.join(os.path.dirname(settings.UPLOAD_DIR), "chunks_corpus.json")


def _atomic_write_json(path: str, data) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return []
    return []


def save_metadata(metadata):
    try:
        os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
        _atomic_write_json(METADATA_FILE, metadata)
    except Exception as e:
        logger.error(f"Failed to save metadata: {e}")


def load_corpus() -> dict:
    if os.path.exists(CORPUS_FILE):
        try:
            with open(CORPUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load corpus: {e}")
    return {}


def save_corpus(corpus: dict):
    try:
        os.makedirs(os.path.dirname(CORPUS_FILE), exist_ok=True)
        _atomic_write_json(CORPUS_FILE, corpus)
    except Exception as e:
        logger.error(f"Failed to save corpus: {e}")


DOCS_METADATA = load_metadata()
CHUNKS_CORPUS = load_corpus()


def _get_embeddings() -> Optional[DashScopeEmbeddings]:
    if not settings.DASHSCOPE_API_KEY:
        return None
    return DashScopeEmbeddings(
        model=settings.EMBEDDING_MODEL,
        dashscope_api_key=settings.DASHSCOPE_API_KEY,
    )


class DocService:
    @staticmethod
    async def process_doc(file: UploadFile) -> UploadResponse:
        if not os.path.exists(settings.UPLOAD_DIR):
            os.makedirs(settings.UPLOAD_DIR)

        file_ext = os.path.splitext(file.filename)[1].lower()
        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id}_{file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(f"File save error: {e}")
            raise HTTPException(status_code=500, detail="File save failed")

        try:
            chunks = DocService._make_chunks(file_path, doc_id, file.filename)
            if not chunks:
                raise ValueError("Empty content")
        except Exception as e:
            logger.error(f"Parse/split error: {e}")
            raise HTTPException(status_code=400, detail=f"File parse failed: {e}")

        total_text_len = sum(len(c.page_content) for c in chunks)
        logger.info(f"Generated {len(chunks)} chunks for {file.filename}")

        vector_status = "解析成功(未向量化)"
        chunk_ids: list[str] = []
        embeddings = _get_embeddings()
        if embeddings is not None:
            try:
                chunk_ids = DocService._add_chunks(chunks, embeddings)
                vector_status = "已索引"
            except Exception as e:
                logger.error(f"Vectorization error: {e}")
                vector_status = "向量化失败"
        else:
            logger.warning("No DASHSCOPE_API_KEY found. Skipping vectorization.")

        doc_meta = {
            "id": doc_id,
            "name": file.filename,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": vector_status,
            "size": os.path.getsize(file_path),
            "path": file_path,
            "chunk_ids": chunk_ids,
        }
        DOCS_METADATA.append(doc_meta)
        save_metadata(DOCS_METADATA)

        return UploadResponse(
            status="success",
            doc_id=doc_id,
            length=total_text_len,
            message="Document processed successfully",
        )

    @staticmethod
    def delete_doc(doc_id: str, background_tasks: BackgroundTasks) -> bool:
        doc = next((d for d in DOCS_METADATA if d["id"] == doc_id), None)
        if not doc:
            return False

        file_path = doc.get("path")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")

        chunk_ids = doc.get("chunk_ids") or []
        if chunk_ids:
            DocService._remove_chunks(chunk_ids)
        else:
            # Legacy doc with no chunk_ids: full rebuild is the only safe option.
            logger.warning(
                f"Doc {doc_id} has no chunk_ids (legacy); scheduling full rebuild."
            )
            background_tasks.add_task(DocService.rebuild_index)

        DOCS_METADATA.remove(doc)
        save_metadata(DOCS_METADATA)
        return True

    @staticmethod
    def reindex_doc(doc_id: str) -> bool:
        doc_meta = next((d for d in DOCS_METADATA if d["id"] == doc_id), None)
        if not doc_meta:
            logger.error(f"Doc {doc_id} not found")
            return False

        file_path = doc_meta["path"]
        if not os.path.exists(file_path):
            logger.error(f"File {file_path} not found")
            return False

        embeddings = _get_embeddings()
        if embeddings is None:
            logger.warning("No API KEY during reindex")
            return False

        try:
            old_chunk_ids = doc_meta.get("chunk_ids") or []
            if old_chunk_ids:
                DocService._remove_chunks(old_chunk_ids)

            chunks = DocService._make_chunks(file_path, doc_id, doc_meta["name"])
            if not chunks:
                logger.error("Empty content during reindex")
                return False

            new_chunk_ids = DocService._add_chunks(chunks, embeddings)
            doc_meta["chunk_ids"] = new_chunk_ids
            doc_meta["status"] = "已索引"
            save_metadata(DOCS_METADATA)
            return True
        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            return False

    @staticmethod
    def rebuild_index():
        """Full rebuild: wipe FAISS + corpus, re-process every known file.

        Use sparingly (expensive). Triggered when a legacy doc is deleted, or
        manually via the admin endpoint after a schema upgrade.
        """
        try:
            logger.info("Starting full index rebuild...")
            current_metadata = load_metadata()

            if os.path.exists(settings.VECTOR_DB_DIR):
                try:
                    shutil.rmtree(settings.VECTOR_DB_DIR)
                except Exception as e:
                    logger.warning(f"Failed to clean vector db dir: {e}")

            CHUNKS_CORPUS.clear()
            save_corpus(CHUNKS_CORPUS)

            embeddings = _get_embeddings()
            if embeddings is None:
                logger.warning("Missing API KEY, cannot rebuild index.")
                return

            for d in current_metadata:
                if d.get("status") not in ("已索引", "解析成功(未向量化)"):
                    continue
                file_path = d["path"]
                if not os.path.exists(file_path):
                    file_path = os.path.abspath(file_path)
                if not os.path.exists(file_path):
                    logger.error(f"File not found during rebuild: {file_path}")
                    continue
                try:
                    chunks = DocService._make_chunks(file_path, d["id"], d["name"])
                    chunk_ids = DocService._add_chunks(chunks, embeddings)
                    d["chunk_ids"] = chunk_ids
                    d["status"] = "已索引"
                except Exception as e:
                    logger.error(f"Failed to process {d['name']}: {e}")

            save_metadata(current_metadata)
            # Refresh in-memory copy
            DOCS_METADATA.clear()
            DOCS_METADATA.extend(current_metadata)
            logger.info("Full index rebuild completed.")
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")

    @staticmethod
    def get_doc_path(doc_id: str) -> str:
        doc = next((d for d in DOCS_METADATA if d["id"] == doc_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        file_path = doc.get("path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return file_path

    @staticmethod
    def get_doc_content(doc_id: str) -> str:
        doc = next((d for d in DOCS_METADATA if d["id"] == doc_id), None)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        file_path = doc.get("path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        try:
            return DocParser.parse(file_path)
        except Exception as e:
            logger.error(f"Failed to read doc content: {e}")
            raise HTTPException(status_code=500, detail="Failed to read document content")

    # ----- internal helpers -----

    @staticmethod
    def _make_chunks(file_path: str, doc_id: str, doc_name: str) -> list[Document]:
        """Parse a file and produce chunks with full metadata attached.

        Each chunk metadata: {chunk_id, doc_id, doc_name, page, source}.
        """
        ext = os.path.splitext(file_path)[1].lower()
        pages = DocParser.parse_pages(file_path)
        chunks: list[Document] = []

        if ext in (".md", ".markdown"):
            text = pages[0]["text"] if pages else ""
            page_no = pages[0]["page"] if pages else 1
            headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ]
            md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
            header_docs = md_splitter.split_text(text)
            char_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
            for sub in char_splitter.split_documents(header_docs):
                chunks.append(
                    Document(
                        page_content=sub.page_content,
                        metadata={
                            **(sub.metadata or {}),
                            "doc_id": doc_id,
                            "doc_name": doc_name,
                            "source": doc_name,
                            "page": page_no,
                            "chunk_id": str(uuid.uuid4()),
                        },
                    )
                )
            return chunks

        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        for entry in pages:
            page_no = entry["page"]
            for piece in char_splitter.split_text(entry["text"]):
                chunks.append(
                    Document(
                        page_content=piece,
                        metadata={
                            "doc_id": doc_id,
                            "doc_name": doc_name,
                            "source": doc_name,
                            "page": page_no,
                            "chunk_id": str(uuid.uuid4()),
                        },
                    )
                )
        return chunks

    @staticmethod
    def _add_chunks(chunks: list[Document], embeddings: DashScopeEmbeddings) -> list[str]:
        """Add chunks to FAISS + corpus. Returns the list of chunk_ids."""
        if not chunks:
            return []
        if not os.path.exists(settings.VECTOR_DB_DIR):
            os.makedirs(settings.VECTOR_DB_DIR)

        ids = [c.metadata["chunk_id"] for c in chunks]
        index_file = os.path.join(settings.VECTOR_DB_DIR, "index.faiss")

        if os.path.exists(index_file):
            try:
                vs = FAISS.load_local(
                    settings.VECTOR_DB_DIR,
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                vs.add_documents(chunks, ids=ids)
            except Exception as e:
                logger.error(f"Failed to load vector store, recreating: {e}")
                vs = FAISS.from_documents(chunks, embeddings, ids=ids)
        else:
            vs = FAISS.from_documents(chunks, embeddings, ids=ids)

        vs.save_local(settings.VECTOR_DB_DIR)

        for c in chunks:
            cid = c.metadata["chunk_id"]
            CHUNKS_CORPUS[cid] = {
                "doc_id": c.metadata.get("doc_id"),
                "doc_name": c.metadata.get("doc_name"),
                "page": c.metadata.get("page", 1),
                "text": c.page_content,
            }
        save_corpus(CHUNKS_CORPUS)
        return ids

    @staticmethod
    def _remove_chunks(chunk_ids: list[str]) -> None:
        """Targeted removal from FAISS + corpus. No full rebuild."""
        if not chunk_ids:
            return
        embeddings = _get_embeddings()
        index_file = os.path.join(settings.VECTOR_DB_DIR, "index.faiss")
        if embeddings is not None and os.path.exists(index_file):
            try:
                vs = FAISS.load_local(
                    settings.VECTOR_DB_DIR,
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                # FAISS.delete silently ignores unknown ids
                vs.delete(ids=chunk_ids)
                vs.save_local(settings.VECTOR_DB_DIR)
            except Exception as e:
                logger.error(f"Failed to delete from FAISS: {e}")

        for cid in chunk_ids:
            CHUNKS_CORPUS.pop(cid, None)
        save_corpus(CHUNKS_CORPUS)

    @staticmethod
    def sync_docs_from_disk():
        if not os.path.exists(settings.UPLOAD_DIR):
            return
        existing_files = {doc["path"] for doc in DOCS_METADATA}
        updated = False
        for filename in os.listdir(settings.UPLOAD_DIR):
            if filename == "metadata.json":
                continue
            file_path = os.path.join(settings.UPLOAD_DIR, filename)
            if not os.path.isfile(file_path):
                continue
            if file_path in existing_files:
                continue

            # Filename convention is "{uuid}_{originalname}". Validate the UUID
            # so an arbitrary file dropped into the directory doesn't poison
            # the registry with a fake doc_id.
            parts = filename.split("_", 1)
            doc_id: Optional[str] = None
            original_name = filename
            if len(parts) == 2:
                try:
                    uuid.UUID(parts[0])
                    doc_id = parts[0]
                    original_name = parts[1]
                except ValueError:
                    pass
            if doc_id is None:
                doc_id = str(uuid.uuid4())

            DOCS_METADATA.append(
                {
                    "id": doc_id,
                    "name": original_name,
                    "upload_time": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "status": "未索引",
                    "size": os.path.getsize(file_path),
                    "path": file_path,
                    "chunk_ids": [],
                }
            )
            updated = True

        if updated:
            save_metadata(DOCS_METADATA)

    @staticmethod
    def get_doc_list(page: int = 1, size: int = 6, keyword: str = "") -> DocListResponse:
        DocService.sync_docs_from_disk()
        try:
            filtered_docs = DOCS_METADATA
            if keyword:
                kw = keyword.lower()
                filtered_docs = [doc for doc in DOCS_METADATA if kw in doc["name"].lower()]

            filtered_docs = sorted(
                filtered_docs, key=lambda x: x.get("upload_time", ""), reverse=True
            )

            total = len(filtered_docs)
            start = (page - 1) * size
            paginated_docs = filtered_docs[start : start + size]

            return DocListResponse(
                total=total,
                items=[DocItem(**{k: v for k, v in item.items() if k in DocItem.model_fields})
                       for item in paginated_docs],
                page=page,
                size=size,
            )
        except Exception as e:
            logger.error(f"Error getting doc list: {e}")
            return DocListResponse(total=0, items=[], page=page, size=size)
