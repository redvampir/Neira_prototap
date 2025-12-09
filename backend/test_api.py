#!/usr/bin/env python3
"""
Simple test script for Neira Backend API
Run this after starting the server (python api.py)
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("=" * 60)
    print("Testing /api/health...")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_stats():
    """Test stats endpoint"""
    print("=" * 60)
    print("Testing /api/stats...")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_chat():
    """Test chat endpoint"""
    print("=" * 60)
    print("Testing /api/chat...")
    print("=" * 60)

    message = "Привет, как дела?"
    print(f"Message: {message}")

    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={"message": message}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data['response']}")
        print(f"Model: {data.get('model', 'unknown')}")
        print(f"Timestamp: {data['timestamp']}")
    else:
        print(f"Error: {response.text}")
    print()


def test_memory():
    """Test memory endpoint"""
    print("=" * 60)
    print("Testing /api/memory...")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/memory?limit=5")
    print(f"Status: {response.status_code}")

    data = response.json()
    print(f"Total memories: {data.get('total', 0)}")
    print(f"Recent entries: {len(data.get('recent', []))}")

    if data.get('recent'):
        print("\nLast memory:")
        last = data['recent'][-1]
        print(f"  Text: {last['text'][:100]}...")
        print(f"  Category: {last['category']}")
        print(f"  Importance: {last['importance']}")
    print()


def main():
    """Run all tests"""
    try:
        print("\nNeira Backend API Tests")
        print("Make sure the server is running: python api.py\n")

        # Test health
        try:
            test_health()
        except Exception as e:
            print(f"❌ Health test failed: {e}\n")
            print("Is the server running?")
            sys.exit(1)

        # Test stats
        try:
            test_stats()
        except Exception as e:
            print(f"❌ Stats test failed: {e}\n")

        # Test chat
        try:
            test_chat()
        except Exception as e:
            print(f"❌ Chat test failed: {e}\n")

        # Test memory
        try:
            test_memory()
        except Exception as e:
            print(f"❌ Memory test failed: {e}\n")

        print("=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Check WebSocket: see test_websocket.py example in README")
        print("2. Try interactive docs: http://localhost:8000/docs")
        print("3. Start building frontend!")

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
