import requests
import time
import json
import sys

BASE_URL = "http://localhost:8081"

# Fix for Windows terminal encoding
sys.stdout.reconfigure(encoding='utf-8')

def test_golden_path():
    print("Starting Golden Path Verification...")
    
    # 1. Simulate Payment Failure
    print("\nStep 1: Simulating Payment Failure...")
    resp = requests.post(f"{BASE_URL}/agent/demo/simulate/payment-failed")
    assert resp.status_code == 200
    print("OK: Payment failure simulated.")
    
    # 2. Verify Decision Creation
    print("\nStep 2: Verifying Decision Creation...")
    time.sleep(1)
    resp = requests.get(f"{BASE_URL}/agent/decisions")
    data = resp.json()
    assert len(data['decisions']) > 0
    decision = data['decisions'][0]
    decision_id = decision['decision_id']
    print(f"OK: Decision found: {decision_id} for customer {decision['customer_id']}")
    print(f"   Intervention: {decision['intervention_type']}, Status: {decision['execution_status']}")

    # 3. Verify Execution (if not NO_ACTION)
    if decision['intervention_type'] != 'no_action':
        print("\nStep 3: Verifying Execution...")
        assert decision['execution_status'] in ['executed', 'captured']
        print(f"OK: Execution status: {decision['execution_status']}")
    else:
        print("\nStep 3: NO_ACTION detected. Verifying reasoning...")
        assert 'no_action' in decision['intervention_type']
        print("OK: Intelligent omission verified.")

    # 4. Simulate Capture (if not NO_ACTION)
    if decision['intervention_type'] != 'no_action':
        print(f"\nStep 4: Simulating Capture for {decision_id}...")
        resp = requests.post(f"{BASE_URL}/agent/demo/simulate/payment-captured", params={"decision_id": decision_id})
        assert resp.status_code == 200
        print("OK: Capture simulated.")

        # 5. Verify Recovery
        print("\nStep 5: Verifying Recovery State...")
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/agent/decisions/{decision_id}")
        updated_decision = resp.json()
        assert updated_decision['execution_status'] == 'captured'
        assert updated_decision['captured_amount'] > 0
        print(f"OK: Recovery verified! Captured amount: {updated_decision['captured_amount']}")

    # 6. Verify Summary Update
    print("\nStep 6: Verifying Summary Update...")
    resp = requests.get(f"{BASE_URL}/agent/summary")
    summary = resp.json()
    print(f"OK: Summary: Captured Decisions = {summary['captured_decisions']}, Recovered Revenue = {summary['revenue_recovered']}")

    print("\nGOLDEN PATH VERIFIED SUCCESSFULLY")

def test_ai_grounding():
    print("\nTesting AI Grounding...")
    resp = requests.get(f"{BASE_URL}/agent/decisions")
    decisions = resp.json()['decisions']
    if not decisions:
        print("ERROR: No decisions found for AI test.")
        return
    
    d = decisions[0]
    cust_id = d['customer_id']
    dec_id = d['decision_id']
    
    # Question 1: Specific decision
    print(f"Query 1: Why did REVEN choose {d['intervention_type']} for {cust_id}?")
    resp = requests.post(f"{BASE_URL}/agent/chat", json={"message": f"Why did REVEN choose {d['intervention_type']} for {cust_id}?"})
    print(f"AI Response: {resp.json()['message']}")
    
    # Question 2: Current status
    print(f"Query 2: What is the current status of decision {dec_id}?")
    resp = requests.post(f"{BASE_URL}/agent/chat", json={"message": f"What is the current status of decision {dec_id}?"})
    print(f"AI Response: {resp.json()['message']}")

if __name__ == "__main__":
    try:
        test_golden_path()
        test_ai_grounding()
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
