from __future__ import annotations

import contextlib
import json
import logging

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .config import Settings
from .database import Database
from .schemas import (
    IndicatorCatalogEntry,
    IndicatorHistoryView,
    IndicatorUpsertInput,
    LabReportInput,
    ReferenceRangeInput,
)
from .service import HealthService


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str | None, exempt_paths: set[str] | None = None):
        super().__init__(app)
        self.api_key = api_key
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        if not self.api_key or request.url.path in self.exempt_paths:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if authorization == f"Bearer {self.api_key}":
            return await call_next(request)

        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_mcp_server(service: HealthService) -> FastMCP:
    mcp = FastMCP(
        "Health MCP",
        instructions=(
        "Use this server to store laboratory indicators, register reference ranges, "
            "import patient lab reports, and read historical values with normality status. "
            "Patients are always scoped to an owning Home Assistant user via owner_user_id."
        ),
        stateless_http=True,
        json_response=True,
    )

    @mcp.tool()
    def upsert_indicator_catalog_entry(
        code: str,
        name: str,
        canonical_unit: str | None = None,
        description: str | None = None,
        reference_ranges: list[ReferenceRangeInput] | None = None,
        replace_reference_ranges: bool = True,
    ) -> IndicatorCatalogEntry:
        """Create or update an indicator catalog entry and its reusable reference ranges."""

        return service.upsert_indicator(
            IndicatorUpsertInput(
                code=code,
                name=name,
                canonical_unit=canonical_unit,
                description=description,
                reference_ranges=reference_ranges or [],
                replace_reference_ranges=replace_reference_ranges,
            )
        )

    @mcp.tool()
    def list_indicator_catalog(query: str | None = None, limit: int = 50):
        """List indicator catalog entries, optionally filtered by code or name."""

        return service.list_indicators(query=query, limit=limit)

    @mcp.tool()
    def get_indicator_catalog_entry(code: str) -> IndicatorCatalogEntry:
        """Return one indicator catalog entry together with all configured reference ranges."""

        return service.get_indicator(code)

    @mcp.tool()
    def import_lab_report(report: LabReportInput):
        """Import one patient lab report under a specific owner_user_id and calculate low/normal/high status."""

        return service.import_lab_report(report)

    @mcp.tool()
    def list_user_patients(owner_user_id: str, query: str | None = None, limit: int = 50):
        """List patients that belong to one Home Assistant user."""

        return service.list_user_patients(owner_user_id=owner_user_id, query=query, limit=limit)

    @mcp.tool()
    def get_patient_indicator_history(
        owner_user_id: str,
        patient_external_id: str,
        indicator_code: str,
        limit: int = 20,
    ) -> IndicatorHistoryView:
        """Return a patient's historical values for a single indicator, scoped to one owner_user_id."""

        return service.get_patient_indicator_history(
            owner_user_id=owner_user_id,
            patient_external_id=patient_external_id,
            indicator_code=indicator_code,
            limit=limit,
        )

    @mcp.resource("catalog://indicator/{code}")
    def indicator_catalog_resource(code: str) -> str:
        """Indicator catalog entry as JSON."""

        return service.get_indicator(code).model_dump_json(indent=2)

    @mcp.resource("user://{owner_user_id}/patients")
    def user_patients_resource(owner_user_id: str) -> str:
        """Patients for a user as JSON."""

        return json.dumps(
            [item.model_dump(mode="json") for item in service.list_user_patients(owner_user_id)],
            indent=2,
        )

    @mcp.resource("user://{owner_user_id}/patient/{patient_external_id}/indicator/{indicator_code}")
    def patient_indicator_resource(owner_user_id: str, patient_external_id: str, indicator_code: str) -> str:
        """Patient indicator history as JSON, scoped to one owner_user_id."""

        return service.get_patient_indicator_history(
            owner_user_id=owner_user_id,
            patient_external_id=patient_external_id,
            indicator_code=indicator_code,
        ).model_dump_json(indent=2)

    return mcp


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    _configure_logging(settings.log_level)

    database = Database(settings)
    service = HealthService(database)

    if settings.auto_migrate:
        service.initialize_schema()

    mcp = create_mcp_server(service)

    async def homepage(_: Request) -> JSONResponse:
        return JSONResponse({
            "name": "Health MCP",
            "mcp_endpoint": "/mcp",
            "health_endpoint": "/health",
        })

    async def healthcheck(_: Request) -> JSONResponse:
        service.ping()
        return JSONResponse({"status": "ok"})

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette):
        async with mcp.session_manager.run():
            yield

    middleware = [
        Middleware(
            ApiKeyMiddleware,
            api_key=settings.api_key,
            exempt_paths={"/", "/health"},
        )
    ]

    return Starlette(
        routes=[
            Route("/", homepage),
            Route("/health", healthcheck),
            Mount("/", app=mcp.streamable_http_app()),
        ],
        middleware=middleware,
        lifespan=lifespan,
    )
