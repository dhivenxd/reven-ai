"""FastAPI server for REVEN LLM Agent.

Provides HTTP API for merchant interactions with the LLM agent.
Integrates with existing REVEN webhook server if present.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.llm.agent.core import RevenAgent
from backend.llm.client.gemini_client import GeminiLLMClient
from backend.llm.store.decision_store import InMemoryDecisionStore
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.integrations.razorpay import config as razorpay_config
from backend.reven.reven_engine import run_reven as frozen_run_reven


# ============================================================
# PYDANTIC MODELS
# ============================================================


class ChatRequest(BaseModel):
    """Request for agent chat."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from agent chat."""
    message: str
    session_id: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    status: str
    timestamp: datetime


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    agent_ready: bool
    llm_configured: bool
    razorpay_configured: bool
    timestamp: datetime


class AgentStatusResponse(BaseModel):
    """Agent status response."""
    status: str
    session_count: int
    total_requests: int
    store_size: int
    timestamp: datetime


# ============================================================
# APPLICATION LIFECYCLE
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("🚀 Starting REVEN LLM Agent API...")
    app.state.agent = None
    app.state.store = None
    app.state.session_counter = 0

    try:
        # Initialize components
        app.state.store = InMemoryDecisionStore()
        app.state.gateway = ExecutionGateway()

        # Try to initialize Gemini client
        try:
            llm_client = GeminiLLMClient()
            app.state.agent = RevenAgent(
                llm_client=llm_client,
                decision_store=app.state.store,
                execution_gateway=app.state.gateway,
            )
            print("✅ Gemini LLM client initialized")
        except ValueError as e:
            print(f"⚠️ LLM client not configured: {e}")
            print("ℹ️ Agent will work for testing but won't call LLM API")

        print("✅ REVEN LLM Agent API started successfully")

        yield

    finally:
        # Shutdown
        print("👋 Shutting down REVEN LLM Agent API...")
        if hasattr(app.state, 'agent') and app.state.agent:
            await app.state.agent.llm.close()
        print("✅ REVEN LLM Agent API shut down")


# ============================================================
# FASTAPI APP
# ============================================================


app = FastAPI(
    title="REVEN LLM Agent API",
    description="AI orchestration layer for REVEN revenue recovery",
    version="1.0.0",
    lifespan=lifespan,
)

# Session store for multi-turn conversations
# In production, use database-backed session store
_sessions: dict[str, RevenAgent] = {}


# ============================================================
# DEPENDENCIES
# ============================================================


def get_agent() -> RevenAgent:
    """Get agent instance."""
    if not app.state.agent:
        raise HTTPException(
            status_code=503,
            detail="LLM agent not configured. Set GEMINI_API_KEY environment variable.",
        )
    return app.state.agent


def get_store() -> InMemoryDecisionStore:
    """Get decision store."""
    if not app.state.store:
        raise HTTPException(
            status_code=503,
            detail="Decision store not initialized",
        )
    return app.state.store


# ============================================================
# ENDPOINTS
# ============================================================


@app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    llm_configured = hasattr(app.state, 'agent') and app.state.agent is not None
    razorpay_configured = razorpay_config.is_configured()

    return HealthResponse(
        status="healthy",
        service="reven-llm-agent",
        agent_ready=llm_configured,
        llm_configured=llm_configured,
        razorpay_configured=razorpay_configured,
        timestamp=datetime.now(),
    )


@app.get("/agent/status")
async def agent_status() -> AgentStatusResponse:
    """Get agent status and metrics."""
    store = get_store()
    sessions = len(_sessions)

    # Count requests via session counter
    total_requests = app.state.session_counter

    # Get store size
    # Access private attribute for demo purposes
    store_size = len(getattr(store, '_decisions', {}))

    return AgentStatusResponse(
        status="ready" if app.state.agent else "unconfigured",
        session_count=sessions,
        total_requests=total_requests,
        store_size=store_size,
        timestamp=datetime.now(),
    )


@app.post("/agent/chat")
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the REVEN LLM agent.

    The agent will:
    1. Understand merchant intent
    2. Use safe tools to query recovery data
    3. Explain REVEN decisions (not make them)
    4. Execute only approved decisions (via decision_id)
    """
    app.state.session_counter += 1

    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())[:8]
    if session_id not in _sessions:
        # For now, use global agent for all sessions
        # In production, create per-session agents
        _sessions[session_id] = get_agent()

    agent = _sessions[session_id]

    try:
        # Process message with agent
        response_text = await agent.chat(request.message)

        # For demo, record that a tool might have been used
        # In production, track actual tool calls
        tool_calls = None  # Simplified for demo

        return ChatResponse(
            message=response_text,
            session_id=session_id,
            tool_calls=tool_calls,
            status="success",
            timestamp=datetime.now(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}",
        )


@app.get("/agent/decisions/{customer_id}")
async def get_customer_decisions(customer_id: str) -> dict[str, Any]:
    """
    Get decisions for a customer (direct API, bypassing LLM).

    Useful for debugging and direct queries.
    """
    store = get_store()
    decisions = store.get_decision_by_customer(customer_id, limit=10)

    return {
        "customer_id": customer_id,
        "decisions": [
            {
                "decision_id": d.decision_id,
                "intervention_type": d.intervention_type.value,
                "expected_net_revenue": d.expected_net_revenue,
                "confidence": d.confidence,
                "execution_status": d.execution_status,
                "created_at": d.created_at.isoformat(),
            }
            for d in decisions
        ],
        "count": len(decisions),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/agent/demo/seed")
async def seed_demo_data() -> dict[str, Any]:
    """
    Seed demo data for testing.

    Creates sample REVEN decisions to demonstrate the agent.
    """
    from backend.reven.decision_engine import RevenueDecision
    from backend.reven.economic_engine import InterventionEconomics
    from backend.schemas.streamflix import InterventionType

    store = get_store()

    # Sample decisions
    decisions = [
        RevenueDecision(
            customer_id="cust_demo_001",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=247.50,
            confidence=0.68,
            reason="Payment failure due to expired card. Retry with updated card expected to recover revenue.",
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType.PAYMENT_RETRY,
                    success_probability=0.65,
                    baseline_probability=0.0,
                    gross_revenue_if_success=399.0,
                    baseline_expected_revenue=0.0,
                    expected_revenue=259.35,
                    incremental_lift=0.65,
                    incremental_revenue=259.35,
                    intervention_cost=2.0,
                    offer_cost=0.0,
                    expected_net_revenue=257.35,
                ),
            ],
        ),
        RevenueDecision(
            customer_id="cust_demo_002",
            intervention_type=InterventionType.RENEWAL_REMINDER,
            expected_net_revenue=195.25,
            confidence=0.74,
            reason="Subscription renewal due in 3 days. Reminder increases retention probability by 22%.",
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType.RENEWAL_REMINDER,
                    success_probability=0.88,
                    baseline_probability=0.66,
                    gross_revenue_if_success=399.0,
                    baseline_expected_revenue=263.34,
                    expected_revenue=351.12,
                    incremental_lift=0.22,
                    incremental_revenue=87.78,
                    intervention_cost=1.0,
                    offer_cost=0.0,
                    expected_net_revenue=86.78,
                ),
            ],
        ),
        RevenueDecision(
            customer_id="cust_demo_003",
            intervention_type=InterventionType.NO_ACTION,
            expected_net_revenue=0.0,
            confidence=0.91,
            reason="Customer at low risk. No intervention has positive expected incremental net revenue.",
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType.NO_ACTION,
                    success_probability=0.95,
                    baseline_probability=0.95,
                    gross_revenue_if_success=399.0,
                    baseline_expected_revenue=379.05,
                    expected_revenue=379.05,
                    incremental_lift=0.0,
                    incremental_revenue=0.0,
                    intervention_cost=0.0,
                    offer_cost=0.0,
                    expected_net_revenue=0.0,
                ),
            ],
        ),
    ]

    # Save decisions
    decision_ids = []
    for decision in decisions:
        decision_id = store.save_decision(decision)
        decision_ids.append(decision_id)

    return {
        "status": "seeded",
        "decision_ids": decision_ids,
        "customer_ids": ["cust_demo_001", "cust_demo_002", "cust_demo_003"],
        "message": "Demo data seeded successfully. Decisions available for agent queries.",
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# ERROR HANDLING
# ============================================================


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": str(exc),
            "path": request.url.path,
        },
    )


# ============================================================
# MAIN
# ============================================================


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("REVEN_LLM_PORT", "8080"))
    host = os.environ.get("REVEN_LLM_HOST", "0.0.0.0")

    print(f"Starting REVEN LLM Agent API on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=os.environ.get("REVEN_LLM_DEBUG", "false").lower() == "true",
    )
