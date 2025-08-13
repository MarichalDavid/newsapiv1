import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DB_HOST = os.getenv("POSTGRES_HOST", "db")
    DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    DB_NAME = os.getenv("POSTGRES_DB", "news")
    DB_USER = os.getenv("POSTGRES_USER", "news")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "news")

    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

    USER_AGENT = os.getenv("USER_AGENT", "NewsIA-Bot/1.0 (+contact@example.org)")
    DEFAULT_FREQ_MIN = int(os.getenv("COLLECTOR_DEFAULT_FREQUENCY_MIN", "10"))

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
