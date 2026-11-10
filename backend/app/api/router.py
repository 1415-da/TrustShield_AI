from fastapi import APIRouter

from app.api import admin, analytics, assistant, auth, documents, health, policies, reviewer, tests_center

api_router = APIRouter(prefix="/api")
for module in (health, auth, assistant, policies, documents, reviewer, analytics, tests_center, admin):
    api_router.include_router(module.router)
