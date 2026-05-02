from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from sqlalchemy.engine import URL


def _env_bool(name: str, default: bool) -> bool:
    raw = getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8099
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "health_mcp"
    db_user: str = "health_mcp"
    db_password: str = ""
    api_key: str | None = None
    auto_migrate: bool = True
    log_level: str = "info"

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = getenv("HEALTH_MCP_API_KEY")
        api_key = api_key.strip() if api_key and api_key.strip() else None
        return cls(
            host=getenv("HEALTH_MCP_HOST", "0.0.0.0"),
            port=int(getenv("HEALTH_MCP_PORT", "8099")),
            db_host=getenv("HEALTH_MCP_DB_HOST", "localhost"),
            db_port=int(getenv("HEALTH_MCP_DB_PORT", "3306")),
            db_name=getenv("HEALTH_MCP_DB_NAME", "health_mcp"),
            db_user=getenv("HEALTH_MCP_DB_USER", "health_mcp"),
            db_password=getenv("HEALTH_MCP_DB_PASSWORD", ""),
            api_key=api_key,
            auto_migrate=_env_bool("HEALTH_MCP_AUTO_MIGRATE", True),
            log_level=getenv("HEALTH_MCP_LOG_LEVEL", "info").lower(),
        )

    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

