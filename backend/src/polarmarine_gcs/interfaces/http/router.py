from fastapi import APIRouter

from .routes import bootstrap, catalogue, debug, missions, runtime, support
from .websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(bootstrap.router, tags=["system"])
api_router.include_router(catalogue.router, tags=["catalogue"])
api_router.include_router(runtime.router, tags=["runtime"])
api_router.include_router(missions.router, tags=["missions"])
api_router.include_router(debug.router, tags=["debug"])
api_router.include_router(support.router, tags=["support"])
api_router.include_router(websocket_router, tags=["events"])
