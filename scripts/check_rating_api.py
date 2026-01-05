import requests
import json

# Test что backend вообще работает
try:
    r = requests.get("http://localhost:8001/api/templates", timeout=2)
    print(f"✅ Backend alive: {r.status_code}")
    print(f"Templates: {len(r.json()['templates'])}")
except Exception as e:
    print(f"❌ Backend not responding: {e}")
    exit(1)

# Test GET artifact
artifact_id = "301a366d585b"
try:
    r = requests.get(f"http://localhost:8001/api/artifacts/{artifact_id}")
    print(f"\n✅ GET artifact: {r.status_code}")
    if r.status_code == 200:
        print(f"Template: {r.json()['template_used']}")
except Exception as e:
    print(f"❌ GET failed: {e}")

# Test rating endpoint с разными путями
paths = [
    f"/api/artifacts/{artifact_id}/rate",
    f"/artifacts/{artifact_id}/rate",
]

for path in paths:
    url = f"http://localhost:8001{path}"
    print(f"\nTesting: {url}")
    try:
        response = requests.post(url, json={"rating": 5}, timeout=2)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ SUCCESS: {response.json()}")
            break
        else:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

