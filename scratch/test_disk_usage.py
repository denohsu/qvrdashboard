import sys
import os
import time
import json
import requests

# 讓 import qvrapi 可以找到上一層目錄
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from qvrapi import load_servers_from_file

SERVERLIST = os.path.join(os.path.dirname(__file__), "..", "serverlist.txt")
SID_CACHE  = os.path.join(os.path.dirname(__file__), "sid_cache.json")


# ── SID 快取管理 ─────────────────────────────────────────────────────────────

def load_sid_cache() -> dict:
    """從 sid_cache.json 讀取已儲存的 SID 對照表 {server_name: sid}。"""
    if os.path.exists(SID_CACHE):
        try:
            with open(SID_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_sid_cache(cache: dict):
    """將 SID 對照表寫回 sid_cache.json。"""
    with open(SID_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def ensure_sid(api, name: str, cache: dict) -> str | None:
    """
    確保 api.sid 有效：
      1. 若快取有 SID → 載入後以 renew_sid() 驗證
      2. renew 失敗或無快取 → 以 get_sid() 重新登入
      3. 取得新 SID 後更新快取並存檔
    回傳有效 SID，失敗回傳 None。
    """
    # 1. 從快取還原 SID
    if name in cache:
        api.sid = cache[name]

    # 2. 嘗試 renew（api.get_sid() 內部已整合此邏輯，直接呼叫即可）
    sid = api.get_sid()   # 內部：有 sid → renew → 成功直接用；失敗 → 重新登入

    if sid:
        if cache.get(name) != sid:
            cache[name] = sid
            save_sid_cache(cache)
            print(f"  -> SID 已更新並儲存快取")
        else:
            print(f"  -> SID 快取有效，續用")
    return sid


# ── 主測試邏輯 ────────────────────────────────────────────────────────────────

def test_disk_usage():
    servers = load_servers_from_file(SERVERLIST)
    if not servers:
        print("No servers found in serverlist.txt")
        return

    cache = load_sid_cache()

    for name, api in servers.items():
        print(f"\n{'='*55}")
        print(f"Server : {name} ({api.ip_address}:{api.port})")

        if not api.check_connection():
            print("  -> Connection failed, skip.")
            continue

        sid = ensure_sid(api, name, cache)
        if not sid:
            print("  -> Login failed, skip.")
            continue

        print(f"  -> SID : {sid}")

        for disk_select in ["System", "DataVol1", "DataVol2", "DataVol3"]:
            params = {
                "chart_func": "disk_usage",
                "count": int(24939),
                "disk_select": disk_select,
                "sid": sid,
            }
            url = f"http://{api.ip_address}:{api.port}/cgi-bin/management/chartReq.cgi"
            try:
                r = requests.get(url, params=params, timeout=5)
                print(f"  url=[{url}] parame=[{params}] ")
                print(f"  [{disk_select}] status={r.status_code}  body={r.text[:500]}")
            except Exception as e:
                print(f"  [{disk_select}] error: {e}")


if __name__ == "__main__":
    test_disk_usage()
