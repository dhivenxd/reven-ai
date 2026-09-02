"""Demo script for REVEN LLM Agent.

Demonstrates the agent capabilities without making real API calls.
For live demo, set ANTHROPIC_API_KEY environment variable.
"""

import asyncio
import os
from typing import Optional
import json

from backend.llm.client.gemini_client import GeminiLLMClient
from backend.llm.agent.core import RevenAgent
from backend.llm.store.decision_store import InMemoryDecisionStore
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.reven.decision_engine import RevenueDecision
from backend.reven.economic_engine import InterventionEconomics
from backend.schemas.streamflix import InterventionType


def create_demo_decision_store() -> InMemoryDecisionStore:
    """Create decision store with demo data."""
    store = InMemoryDecisionStore()

    # Demo decision 1: Payment Retry
    decision1 = RevenueDecision(
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
    )

    # Demo decision 2: Renewal Reminder
    decision2 = RevenueDecision(
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
    )

    # Demo decision 3: NO_ACTION
    decision3 = RevenueDecision(
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
    )

    # Save decisions
    store.save_decision(decision1)
    store.save_decision(decision2)
    store.save_decision(decision3)

    # Mark decision1 as executed for demo
    decisions = store.get_decision_by_customer("cust_demo_001", limit=1)
    if decisions:
        store.update_execution_status(
            decisions[0].decision_id,
            status="executed",
            razorpay_result_id="link_demo_123",
        )

    return store


def create_mock_gateway() -> ExecutionGateway:
    """Create mock execution gateway for demo."""
    from backend.integrations.razorpay.execution_gateway import ExecutionGateway, ExecutionResult
    from datetime import datetime

    class MockExecutionGateway(ExecutionGateway):
        def execute_decision(self, decision, subscription, **kwargs):
            return ExecutionResult(
                decision_id=decision.customer_id,
                intervention_type=decision.intervention_type,
                execution_status="executed",
                razorpay_operation="create_payment_link",
                razorpay_resource_id="link_demo_456",
                razorpay_resource_url="https://rzp.io/i/demo_link",
                executed_at=datetime.now(),
                message="Payment recovery link created for demo.",
            )

    return MockExecutionGateway()


async def demo_without_api() -> None:
    """Run demo without live API (test mode)."""
    print("🚀 REVEN LLM Agent Demo (Test Mode)")
    print("=" * 50)
    print()

    # Setup
    store = create_demo_decision_store()
    gateway = create_mock_gateway()

    # Mock LLM client (won't call API)
    print("📦 Setup:")
    print("  - Decision store: created with 3 demo decisions")
    print("  - Mock Execution Gateway: ready")
    print("  - LLM Client: not configured (test mode)")
    print()

    print("🎭 Available demo queries:")
    print("  1. 'What recovery action for cust_demo_001?'")
    print("  2. 'Execute the payment retry for cust_demo_001'")
    print("  3. 'Show me recovery summary'")
    print("  4. 'What happened with cust_demo_003?'")
    print()

    print("📈 Current decisions:")
    for customer_id in ["cust_demo_001", "cust_demo_002", "cust_demo_003"]:
        decisions = store.get_decision_by_customer(customer_id, limit=1)
        if decisions:
            d = decisions[0]
            print(f"  - {customer_id}: {d.intervention_type.value} (status: {d.execution_status})")

    print()
    print("ℹ️ For live LLM demo, set GEMINI_API_KEY environment variable.")
    print("   Then run: python backend/llm/demo.py --live")
    print()


async def demo_with_live_api() -> None:
    """Run demo with live Gemini API."""
    print("🚀 REVEN LLM Agent Demo (Live API)")
    print("=" * 50)
    print()

    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set.")
        print("   Set it with your Gemini API key to run live demo.")
        print("   Example: export GEMINI_API_KEY='your-key-here'")
        return

    # Setup
    store = create_demo_decision_store()
    gateway = create_mock_gateway()

    try:
        llm_client = GeminiLLMClient()
        agent = RevenAgent(llm_client, store, gateway)

        print("✅ Setup complete:")
        print("  - Gemini LLM client: ready")
        print("  - Decision store: 3 demo decisions loaded")
        print("  - Mock Execution Gateway: ready")
        print()

        # Demo conversation
        queries = [
            "What recovery action was taken for cust_demo_001?",
            "Execute the approved recovery for cust_demo_002",
            "Show me recovery metrics for this month",
            "What about cust_demo_003?",
        ]

        for i, query in enumerate(queries):
            print(f"🤔 Query {i+1}: {query}")
            print("-" * 30)

            response = await agent.chat(query)
            print(f"🤖 Response: {response}")
            print()

            if i < len(queries) - 1:
                input("Press Enter for next query...")
                print()

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print()
        print("Debug info:")
        print(f"  API Key: {'Set' if api_key else 'Not set'}")
        print(f"  Error: {type(e).__name__}")
        if "API key" in str(e):
            print("  ⚠️ Check your GEMINI_API_KEY")


async def demo_agent_chat() -> None:
    """Interactive chat demo."""
    print("💬 REVEN LLM Agent Interactive Demo")
    print("=" * 50)
    print()
    print("This is an interactive chat with the REVEN LLM agent.")
    print("The agent can only use safe tools and cannot make financial decisions.")
    print("Type 'quit' to exit.")
    print()

    # Setup
    store = create_demo_decision_store()
    gateway = create_mock_gateway()

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            llm_client = GeminiLLMClient()
            agent = RevenAgent(llm_client, store, gateway)
            print("✅ Live agent ready (using Gemini API)")
        except Exception as e:
            print(f"⚠️ Could not initialize live agent: {e}")
            print("  Continuing in test mode (mock responses)")
            agent = None
    else:
        print("ℹ️ No API key set. Running in test mode.")
        print("  Set GEMINI_API_KEY for live agent responses.")
        agent = None

    print()
    print("Example queries:")
    print("  - 'What happened with customer cust_demo_001?'")
    print("  - 'Show me recovery summary'")
    print("  - 'Execute the payment retry for cust_demo_002'")
    print("  - 'Why did REVEN choose that action?'")
    print()

    while True:
        try:
            query = input("You: ").strip()
            if query.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not query:
                continue

            if agent:
                # Live agent response
                response = await agent.chat(query)
                print(f"Agent: {response}")
            else:
                # Mock responses based on query
                if "cust_demo_001" in query:
                    print("Agent: REVEN approved a PAYMENT_RETRY for cust_demo_001 with 68% confidence. Expected net revenue: ₹247.50. Payment link created.")
                elif "cust_demo_002" in query and "execute" in query.lower():
                    print("Agent: Executing approved RENEWAL_REMINDER for cust_demo_002. Creating notification...")
                elif "summary" in query.lower():
                    print("Agent: 3 decisions total, 1 executed, 0 revenue actually recovered yet (payment links created).")
                elif "cust_demo_003" in query:
                    print("Agent: REVEN determined NO_ACTION for cust_demo_003 (91% confidence). No recovery action needed at this time.")
                else:
                    print("Agent: I can help you query recovery status, explain REVEN decisions, or execute approved actions. What would you like to know?")

            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="REVEN LLM Agent Demo")
    parser.add_argument(
        "--mode",
        choices=["test", "live", "chat"],
        default="test",
        help="Demo mode: test (no API), live (with Claude), chat (interactive)",
    )

    args = parser.parse_args()

    try:
        if args.mode == "test":
            asyncio.run(demo_without_api())
        elif args.mode == "live":
            asyncio.run(demo_with_live_api())
        elif args.mode == "chat":
            asyncio.run(demo_agent_chat())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"Demo error: {e}")
