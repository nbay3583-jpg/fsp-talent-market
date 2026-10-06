from typing import Final

from fastapi import FastAPI
from pydantic import BaseModel

from fsp_market import __version__
from fsp_market.api.employer_routes import router as employer_router
from fsp_market.api.routes import router as api_router
from fsp_market.config import get_settings


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


app: Final = FastAPI(
    title=get_settings().app_name,
    version=__version__,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=get_settings().app_name,
        version=__version__,
    )


app.include_router(api_router)
app.include_router(employer_router)
