"""
Health check route.

Simple endpoint for load balancers, monitoring, and deployment readiness
checks.  Returns {"status": "ok"} when the server is running.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Return a simple health status for uptime monitoring."""
    return {"status": "ok"}
