from fastapi import APIRouter
from app.api import auth, clients, inventory

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
