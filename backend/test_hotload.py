"""Test hot load functionality"""
import requests
import json

BASE_URL = "http://localhost:8888"

def test_hot_load():
    """Test hot loading a plugin"""
    print("=" * 60)
    print("Testing AstrBot Plugin Hot Load")
    print("=" * 60)
    
    # 1. Check loaded plugins
    print("\n1. Checking loaded AstrBot plugins...")
    r = requests.get(f"{BASE_URL}/api/plugins/astrbot_compatibility/loaded")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Loaded plugins: {len(data.get('plugins', []))}")
        for p in data.get('plugins', []):
            print(f"      - {p['name']}")
    
    # 2. Try to hot load test plugin
    print("\n2. Attempting to hot load test_hotload_plugin...")
    r = requests.post(
        f"{BASE_URL}/api/plugins/astrbot_compatibility/hot_load",
        json={'plugin_name': 'test_hotload_plugin'}
    )
    print(f"   Status: {r.status_code}")
    print(f"   Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
    
    # 3. Check loaded plugins again
    print("\n3. Checking loaded plugins after hot load...")
    r = requests.get(f"{BASE_URL}/api/plugins/astrbot_compatibility/loaded")
    if r.status_code == 200:
        data = r.json()
        print(f"   Loaded plugins: {len(data.get('plugins', []))}")
        for p in data.get('plugins', []):
            print(f"      - {p['name']}")
    
    # 4. Try to hot unload
    print("\n4. Attempting to hot unload test_hotload_plugin...")
    r = requests.post(
        f"{BASE_URL}/api/plugins/astrbot_compatibility/hot_unload",
        json={'plugin_name': 'test_hotload_plugin'}
    )
    print(f"   Status: {r.status_code}")
    print(f"   Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_hot_load()
