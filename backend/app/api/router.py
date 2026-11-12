from fastapi import APIRouter

from app.api import admin, agents, guard, analytics, assistant, auth, compliance, documents, health, integrations, organizations, policies, reviewer, tests_center

api_router = APIRouter(prefix="/api")
for module in (health, auth, assistant, policies, documents, reviewer, analytics, tests_center, admin, compliance, integrations, agents, organizations, guard):
    api_router.include_router(module.router)
