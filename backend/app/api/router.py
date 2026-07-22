from fastapi import APIRouter

from app.api.routes import commands, connections, health, logs, parameters, robots

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(robots.router, prefix="/robots", tags=["robots"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(logs.router, tags=["logs"])
api_router.include_router(parameters.router, prefix="/parameters", tags=["parameters"])
api_router.include_router(commands.router, prefix="/commands", tags=["commands"])
