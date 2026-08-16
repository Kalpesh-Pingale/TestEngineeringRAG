import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env first with override=True so .env values win over system env vars
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)


class Settings(BaseSettings):
    # Jira
    jira_base_url: str = ""
    jira_project_key: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_mcp_server: str = "http://localhost:8080"
    jira_use_mcp: bool = True

    # TestRail
    testrail_base_url: str = ""
    testrail_enabled: bool = True
    testrail_project_id: int = 1
    testrail_suite_id: int = 1
    testrail_section_id: int = 1
    testrail_username: str = ""
    testrail_api_key: str = ""
    testrail_mcp_server: str = "http://localhost:8090"

    # Vector DB
    vector_db: str = "chromadb"
    chroma_db_path: str = "./chromadb"

    # Embedding — fastembed runs locally via ONNX: no server, no API key, no GPU.
    embedding_provider: str = "fastembed"
    # Changing this invalidates every stored vector. Vectors are stamped with the
    # model that produced them and a mismatch blocks queries until a Full Sync.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Persist the ONNX model outside the OS temp dir so it survives cleanup
    # and is not re-downloaded on every boot.
    fastembed_cache_dir: str = "./model_cache"

    # LLM
    llm_provider: str = "groq"
    llm_model: str = "opengpt-oss-120b"
    groq_api_key: str = ""

    # Sync
    enable_incremental_sync: bool = True
    sync_interval_minutes: int = 30
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k_results: int = 5

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:3000"


settings = Settings()
