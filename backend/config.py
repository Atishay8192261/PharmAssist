import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")
    ENV: str = os.getenv("FLASK_ENV", "development")


def get_config() -> "Config":
    return Config()
