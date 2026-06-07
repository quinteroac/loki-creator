from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.env import load_dotenv


load_dotenv()

from app.api import router  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(title="Loki Creator API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    return app


app = create_app()
