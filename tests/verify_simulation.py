import asyncio
from fastapi.testclient import TestClient
from backend.llm.api.server import app
from backend.llm.store.shared import get_shared_store

client = TestClient(app)

async def test_simulation():
    print("Testing Simulation Flow...")
    
    # 1. Simulate Failure
    resp = client.post("/agent/demo/simulate/payment-failed")
    print(f"Simulate Failure: {resp.status_code} - {resp.json()}")
    assert resp.status_code == 200
    
    # 2. Check if decision was created
    dec_resp = client.get("/agent/decisions")
    decisions = dec_resp.json()["decisions"]
    assert len(decisions) > 0
    last_dec_id = decisions[0]["decision_id"]
    print(f"New Decision Created: {last_dec_id}")
    
    # 3. Simulate Capture
    cap_resp = client.post(f"/agent/demo/simulate/payment-captured?decision_id={last_dec_id}")
    print(f"Simulate Capture: {cap_resp.status_code} - {cap_resp.json()}")
    assert cap_resp.status_code == 200
    
    # 4. Verify capture in store
    detail_resp = client.get(f"/agent/decisions/{last_dec_id}")
    detail = detail_resp.json()
    print(f"Final Status: {detail['execution_status']}")
    assert detail["execution_status"] == "captured"
    print("Simulation flow verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_simulation())
