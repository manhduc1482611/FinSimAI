from fastapi import APIRouter

from api.v1.auth import router as auth_router
from api.v1.companies import router as companies_router
from api.v1.knowledge import router as knowledge_router
from api.v1.news import router as news_router
from api.v1.risk import router as risk_router
from api.v1.social import router as social_router
from api.v1.trades import router as trades_router
from api.v1.users import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(companies_router)
api_router.include_router(trades_router)
api_router.include_router(knowledge_router)
api_router.include_router(news_router)
api_router.include_router(risk_router)
api_router.include_router(social_router)
