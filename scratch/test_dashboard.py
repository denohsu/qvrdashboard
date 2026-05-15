import urllib.request
import json

try:
    req = urllib.request.Request("http://127.0.0.1:9999/api/dashboard_data")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        for s in data.get("servers", []):
            print(f"Server: {s['name']}")
            print(f"  disk_usage: {s.get('disk_usage', 'MISSING')}")
except Exception as e:
    print(f"Error: {e}")
