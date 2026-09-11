import requests
import sys
import time

API_URL = "http://localhost:8000/v1/ask"

def run_sequence(sequence):
    conversation_id = None
    for turn in sequence:
        payload = {"question": turn["question"]}
        if conversation_id:
            payload["conversation_id"] = conversation_id
            
        print(f"User: {turn['question']}")
        resp = requests.post(API_URL, json=payload)
        
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} {resp.text}")
            sys.exit(1)
            
        data = resp.json()
        conversation_id = data.get("conversation_id")
        print(f"Assistant: {data.get('answer')[:100]}...\n")
        
        expected = turn.get("expected_in_answer")
        if expected and expected.lower() not in data.get('answer', '').lower():
            print(f"FAILED: Expected '{expected}' in answer")
            sys.exit(1)

        time.sleep(1)

def main():
    print("Running Multi-Turn Evals...")
    
    # Sequence 1: Stop -> Continue
    # Since we can't easily simulate Stop from a synchronous script (requires cancelling request),
    # we just run basic multi-turn condensation checks.
    
    seq1 = [
        {"question": "What is the critical response time for Platinum tier?", "expected_in_answer": "15"},
        {"question": "What about for Gold?", "expected_in_answer": "30"} # Should condense to "What is the critical response time for Gold tier?"
    ]
    
    run_sequence(seq1)
    print("Multi-turn eval passed.")

if __name__ == "__main__":
    main()
