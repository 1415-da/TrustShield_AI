from fastapi import APIRouter

from app.api import admin, agents, analytics, assistant, auth, compliance, documents, health, integrations, policies, reviewer, tests_center

api_router = APIRouter(prefix="/api")
for module in (health, auth, assistant, policies, documents, reviewer, analytics, tests_center, admin, compliance, integrations, agents):
    api_router.include_router(module.router)
