import sys
import os
import time
import re
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from qvrapi import load_servers_from_file

SERVERLIST = os.path.join(os.path.dirname(__file__), "..", "serverlist.txt")


def _extract(text: str, tag: str) -> str | None:
    pattern = rf'<{re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{re.escape(tag)}>'
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_int(text: str, tag: str, default: int = 0) -> int:
    v = _extract(text, tag)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def get_memory_info(api) -> dict | None:
    url = f"http://{api.ip_address}:{api.port}/cgi-bin/management/manaRequest.cgi"
    params = {
        "subfunc":        "sysmonitor",
        "sys_memory_use": "1",
        "count":          int(time.time() * 1000),
        "sid":            api.sid,
    }
    print(f"url: {url}, params: {params}") 
    try:
        r = requests.get(url, params=params, timeout=10)
        raw = r.text
    except Exception as e:
        print(f"  [memory] 連線失敗: {e}")
        return None

    auth = _extract(raw, "authPassed")
    if auth != "1":
        print(f"  [memory] authPassed={auth}，SID 無效")
        return None

    total = _extract_int(raw, "mem_total")
    used  = _extract_int(raw, "mem_used")
    free  = _extract_int(raw, "mem_free")

    if total == 0:
        all_tags = re.findall(r'<([a-z_][a-z0-9_]*)>\s*(?:<!\[CDATA\[)?\s*(\d+)\s*(?:\]\]>)?\s*</\1>', raw, re.IGNORECASE)
        print(f"  [memory] 找不到 mem_total，數字型 tag: {all_tags[:30]}")
        return None

    # 若 API 未回傳 used，自行計算
    if used == 0 and total > 0 and free > 0:
        used = total - free

    pct = round(used / total * 100, 1) if total else 0

    return {
        "total": total,
        "used":  used,
        "free":  free,
        "pct":   pct,
    }


def print_memory_info(name: str, ip: str, info: dict):
    bar_len = 30
    filled  = round(info["pct"] / 100 * bar_len)
    bar     = "█" * filled + "░" * (bar_len - filled)

    print(f"\n{'='*55}")
    print(f"  Server  : {name} ({ip})")
    print(f"  Total   : {info['total']} KB")
    print(f"  Used    : {info['used']} KB")
    print(f"  Free    : {info['free']} KB")
    print(f"  Usage   : [{bar}] {info['pct']} %")


def main():
    servers = load_servers_from_file(SERVERLIST)
    if not servers:
        print("No servers found in serverlist.txt")
        return

    for name, api in servers.items():
        print(f"\nConnecting to {name} ({api.ip_address}:{api.port}) ...")

        if not api.check_connection():
            print("  -> Connection failed, skip.")
            continue

        if not api.get_sid():
            print("  -> Login failed, skip.")
            continue

        info = get_memory_info(api)
        if info:
            print_memory_info(name, api.ip_address, info)


if __name__ == "__main__":
    main()
