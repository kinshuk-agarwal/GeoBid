from fastapi import APIRouter

from app.api import auctions, auth, dashboard, footfall, health, inventory, map, poles

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(poles.router)
api_router.include_router(map.router)
api_router.include_router(footfall.router)
api_router.include_router(inventory.router)
api_router.include_router(auctions.router)
api_router.include_router(dashboard.router)
