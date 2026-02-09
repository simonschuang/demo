from fastapi import APIRouter
from app.api import auth, clients, inventory
from app import __version__, __build_time__

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])


@api_router.get("/version", tags=["system"])
async def get_version():
    """Get server version information"""
    return {
        "name": "Agent Monitor Server",
        "version": __version__,
        "build_time": __build_time__
    }
