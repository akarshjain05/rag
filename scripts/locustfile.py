from locust import HttpUser, task, between

class RAGUser(HttpUser):
    # Simulate a user thinking for 1 to 5 seconds before asking a new question
    wait_time = between(1, 5)

    @task
    def ask_question(self):
        # We simulate a typical question to the /v1/ask endpoint
        payload = {
            "question": "What is the critical-severity response time for Platinum tier?"
        }
        
        # Catch-response allows us to inspect the result and mark failure based on context
        with self.client.post("/v1/ask", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data:
                    response.success()
                else:
                    response.failure(f"Missing answer in response: {response.text}")
            elif response.status_code == 504:
                response.failure("504 Gateway Timeout - The proxy dropped the connection!")
            else:
                response.failure(f"Unexpected status code: {response.status_code} - {response.text}")
