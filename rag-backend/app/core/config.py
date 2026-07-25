from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import yaml
import os

# Resolve paths relative to this file so that .env and app.yaml are found
# regardless of CWD.  Storage paths (VECTOR_DB_DIR, UPLOAD_DIR) are kept
# relative on purpose — FAISS's C++ backend cannot open files whose absolute
# path contains non-ASCII characters (e.g. Chinese), so those paths stay
# relative and rely on start.py's os.chdir() to resolve correctly.
_BASE_DIR = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))  # app\core
_PROJECT_ROOT = os.path.normpath(os.path.dirname(os.path.dirname(_BASE_DIR)))  # rag-backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.normpath(os.path.join(_PROJECT_ROOT, ".env")),
        extra="ignore",
    )

    # App
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "RAG Backend"

    # Storage — kept RELATIVE so FAISS's C++ backend can open them even when
    # the project resides in a path with non-ASCII characters.
    UPLOAD_DIR: str = "data/docs"
    VECTOR_DB_DIR: str = "data/vector_db"

    # Model (DashScope)
    DASHSCOPE_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-v3"
    LLM_MODEL: str = "qwen3.7-plus"
    RERANK_MODEL: str = "qwen3-rerank"

    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # Retrieval
    TOP_K: int = 3                       # Final number of contexts fed to the LLM
    VECTOR_CANDIDATES: int = 20          # Candidates pulled from FAISS before fusion/rerank
    BM25_CANDIDATES: int = 20            # Candidates pulled from BM25 before fusion/rerank
    ENABLE_HYBRID: bool = True           # Vector + BM25 with RRF fusion
    ENABLE_RERANK: bool = True           # Cross-encoder rerank after fusion
    RRF_K: int = 60                      # Reciprocal Rank Fusion constant
    RELEVANCE_THRESHOLD: float = 0.2     # Drop chunks with rerank/relevance < threshold

    @classmethod
    def load_from_yaml(cls, path: str = None):
        if path is None:
            path = os.path.normpath(os.path.join(_PROJECT_ROOT, "config", "app.yaml"))
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:
            return cls()

        overrides: dict = {}
        if "model" in config_data:
            mc = config_data["model"]
            if isinstance(mc.get("embedding"), dict) and mc["embedding"].get("model_name"):
                overrides["EMBEDDING_MODEL"] = mc["embedding"]["model_name"]
            if isinstance(mc.get("llm"), dict) and mc["llm"].get("model_name"):
                overrides["LLM_MODEL"] = mc["llm"]["model_name"]
            if isinstance(mc.get("rerank"), dict) and mc["rerank"].get("model_name"):
                overrides["RERANK_MODEL"] = mc["rerank"]["model_name"]

        if "vector_db" in config_data:
            vd = config_data["vector_db"]
            if vd.get("path"):
                # Keep as-is from YAML — must stay relative for FAISS C++ compat
                # (absolute paths with non-ASCII chars break FAISS on Windows).
                overrides["VECTOR_DB_DIR"] = vd["path"]
            if vd.get("top_n") is not None:
                overrides["TOP_K"] = vd["top_n"]

        if "splitter" in config_data:
            sp = config_data["splitter"]
            if sp.get("chunk_size") is not None:
                overrides["CHUNK_SIZE"] = sp["chunk_size"]
            if sp.get("overlap") is not None:
                overrides["CHUNK_OVERLAP"] = sp["overlap"]

        if "retrieval" in config_data:
            rt = config_data["retrieval"]
            for yaml_key, settings_key in (
                ("vector_candidates", "VECTOR_CANDIDATES"),
                ("bm25_candidates", "BM25_CANDIDATES"),
                ("enable_hybrid", "ENABLE_HYBRID"),
                ("enable_rerank", "ENABLE_RERANK"),
                ("rrf_k", "RRF_K"),
                ("relevance_threshold", "RELEVANCE_THRESHOLD"),
            ):
                if rt.get(yaml_key) is not None:
                    overrides[settings_key] = rt[yaml_key]

        return cls(**overrides)


@lru_cache()
def get_settings():
    return Settings.load_from_yaml()
