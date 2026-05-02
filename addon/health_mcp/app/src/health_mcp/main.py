from __future__ import annotations

import uvicorn

from .config import Settings
from .server import create_app


def main() -> None:
    settings = Settings.from_env()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)

