import httpx
import json

data = {
    "repo_name": "test-repo",
    "description": "A test project",
    "tech_stack": ["python"],
    "stars": 10,
    "forks": 5,
    "readme": "test"
}

try:
    print("Sending request...")
    r = httpx.post("http://localhost:8000/api/suggest-companies", json=data, timeout=300.0)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
