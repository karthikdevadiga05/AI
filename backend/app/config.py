import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./data/citewise.db')
    data_dir: Path = Path(os.getenv('DATA_DIR', './data'))
    ai_mode: str = os.getenv('AI_MODE', 'excerpt')
    ollama_url: str = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    chat_model: str = os.getenv('CHAT_MODEL', 'llama3.2:3b')
    embed_model: str = os.getenv('EMBED_MODEL', 'nomic-embed-text')
    embed_dim: int = int(os.getenv('EMBED_DIM', '768'))
    cookie_secure: bool = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
    app_origin: str = os.getenv('APP_ORIGIN', 'http://localhost:8000')
    max_upload: int = 20 * 1024 * 1024
    max_pages: int = 200
    max_chunks: int = 1500
    max_documents: int = 30

    def __post_init__(self):
        if self.ai_mode not in {'excerpt', 'ollama'}:
            raise ValueError('AI_MODE must be excerpt or ollama')
