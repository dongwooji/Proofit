"""FastAPI app. Routers stay thin: they call the service layer and commit."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from proofit import __version__
from proofit.api.routers import applications, candidate, jobs
from proofit.errors import ConflictError, DomainError, NotFoundError

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status, content={"error": {"code": code, "message": message}}
    )


async def _domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    http_status = next(
        (code for cls, code in _STATUS_BY_ERROR.items() if isinstance(exc, cls)),
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return _error(exc.code, exc.message, http_status)


async def _integrity_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    # Last-resort guard (e.g. a concurrent duplicate); services check rules first.
    return _error(
        "integrity_error",
        "데이터 무결성 규칙에 맞지 않아 저장하지 못했습니다.",
        status.HTTP_409_CONFLICT,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Proofit", version=__version__)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(IntegrityError, _integrity_error_handler)
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(candidate.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
