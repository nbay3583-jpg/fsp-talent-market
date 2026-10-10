from typing import Final

from fastapi import FastAPI
from pydantic import BaseModel

from fsp_market import __version__
from fsp_market.api.auth_routes import router as auth_router
from fsp_market.api.demo_routes import router as demo_router
from fsp_market.api.employer_routes import router as employer_router
from fsp_market.api.invitation_routes import router as invitation_router
from fsp_market.api.routes import router as api_router
from fsp_market.api.validation_routes import router as validation_router
from fsp_market.assistant.routes import router as assistant_router
from fsp_market.config import get_settings
from fsp_market.experience.routes import router as experience_router
from fsp_market.teamfit.routes import router as teamfit_router


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def assert_safe_configuration() -> None:
    """Refuse to start in a production environment with demo features or the default token secret."""
    settings = get_settings()
    if settings.environment.lower() in {"production", "prod"} and (
        settings.demo_mode or settings.jwt_secret.startswith(("dev-only", "change-me"))
    ):
        raise RuntimeError(
            "unsafe configuration: set DEMO_MODE=false and a real JWT_SECRET in production"
        )


assert_safe_configuration()

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
app.include_router(auth_router)
app.include_router(employer_router)
app.include_router(invitation_router)
app.include_router(experience_router)
app.include_router(teamfit_router)
app.include_router(assistant_router)
app.include_router(demo_router)
app.include_router(validation_router)
