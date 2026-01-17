"""
Webhook endpoints for external integrations.

Provides endpoints for Gmail webhooks and other third-party integrations.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# TODO: Implement webhook endpoints in Phase 2
# - POST /email - Gmail Pub/Sub webhook for email ingestion
