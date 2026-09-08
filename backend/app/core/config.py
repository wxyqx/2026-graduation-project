from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/ats?charset=utf8mb4"

    model_config = {
        "env_file": Path(__file__).resolve().parents[2] / ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
