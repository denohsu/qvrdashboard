import sys
import os
import time
import re
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from qvrapi import load_servers_from_file

SERVERLIST = os.path.join(os.path.dirname(__file__), "..", "serverlist.txt")


# ── XML 解析輔助 ──────────────────────────────────────────────────────────────

def _extract(text: str, tag: str) -> str | None:
    """從 XML 文字中擷取指定 tag 的值（支援 CDATA 與純文字）。"""
    pattern = rf'<{re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{re.escape(tag)}>'
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_int(text: str, tag: str, default: int = 0) -> int:
    v = _extract(text, tag)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def _extract_float(text: str, tag: str, default: float = 0.0) -> float:
    v = _extract(text, tag)
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default


# ── 查詢系統資訊 ──────────────────────────────────────────────────────────────

def _find_memory_tags(raw: str) -> tuple[int, int]:
    """嘗試多種 tag 名稱取得 total / free memory (MB)。"""
    for total_tag, free_tag in [
        ("total_memory",  "free_memory"),
        ("totalram",      "freeram"),
        ("mem_total",     "mem_free"),
        ("total_mem",     "free_mem"),
        ("physicalmemory","freememory"),
        ("memtotal",      "memfree"),
    ]:
        total = _extract_int(raw, total_tag, -1)
        free  = _extract_int(raw, free_tag,  -1)
        if total > 0:
            return total, max(free, 0)

    # 找不到時印出所有數字型 tag 協助排查
    all_num_tags = re.findall(r'<([a-z_][a-z0-9_]*)>\s*(?:<!\[CDATA\[)?\s*(\d+)\s*(?:\]\]>)?\s*</\1>', raw, re.IGNORECASE)
    print(f"  [sysinfo] 找不到 memory tag，數字型 tag 清單: {all_num_tags[:30]}")
    return 0, 0


def get_system_info(api) -> dict | None:
    """
    呼叫 manaRequest.cgi?subfunc=sysinfo 取得系統資訊。
    回傳解析後的 dict，失敗回傳 None。
    """
    url = f"http://{api.ip_address}:{api.port}/cgi-bin/management/manaRequest.cgi"
    params = {
        "subfunc": "sysinfo",
        "count": int(time.time() * 1000),
        "sid": api.sid,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        raw = r.text
    except Exception as e:
        print(f"  [sysinfo] 連線失敗: {e}")
        return None

    auth = _extract(raw, "authPassed")
    if auth != "1":
        print(f"  [sysinfo] authPassed={auth}，SID 無效")
        return None

    total_mem, free_mem = _find_memory_tags(raw)

    # CPU usage 去除已含的 % 符號
    cpu_raw = _extract(raw, "cpu_usage") or "0"
    cpu_usage = cpu_raw.replace("%", "").strip()

    # ── 系統與運行資訊 ────────────────────────────────────────────────────────
    info = {
        "server_name":   _extract(raw, "server_name"),
        "serial_number": _extract(raw, "serial_number"),
        "uptime": {
            "day":  _extract_int(raw, "uptime_day"),
            "hour": _extract_int(raw, "uptime_hour"),
            "min":  _extract_int(raw, "uptime_min"),
            "sec":  _extract_int(raw, "uptime_sec"),
        },
        # ── CPU 與記憶體 ──────────────────────────────────────────────────────
        "cpu_usage":    cpu_usage,
        "total_memory": total_mem,
        "free_memory":  free_mem,
        # ── 硬碟數量 ─────────────────────────────────────────────────────────
        "disk_num":    _extract_int(raw, "disk_num"),
        "ssd_num":     _extract_int(raw, "ssd_disk_num"),
        "m2_num":      _extract_int(raw, "m2_disk_num"),
        # ── 溫度 ─────────────────────────────────────────────────────────────
        "cpu_tempc": _extract(raw, "cpu_tempc"),
        "sys_tempc": _extract(raw, "sys_tempc"),
        # ── 網路 ─────────────────────────────────────────────────────────────
        "nic_cnt": _extract_int(raw, "nic_cnt"),
    }

    # 各顆硬碟溫度（最多掃 32 顆）
    disk_temps = []
    for no in range(32):
        tc = _extract(raw, f"tempc{no}")
        if tc is None:
            break
        disk_temps.append({"no": no, "tempc": tc, "tempf": _extract(raw, f"tempf{no}")})
    info["disk_temps"] = disk_temps

    # 風扇轉速（最多掃 8 個）
    fans = []
    for no in range(8):
        rpm = _extract(raw, f"sysfan{no}")
        if rpm is None:
            break
        fans.append({"no": no, "rpm": rpm})
    info["fans"] = fans

    # 網卡狀態（最多掃 8 張）
    nics = []
    for no in range(info["nic_cnt"] or 8):
        status = _extract(raw, f"eth_status{no}")
        if status is None:
            break
        nics.append({
            "no":        no,
            "status":    "Connected" if status == "1" else "Disconnected",
            "mac":       _extract(raw, f"eth_mac{no}"),
            "rx_packet": _extract(raw, f"rx_packet{no}"),
            "tx_packet": _extract(raw, f"tx_packet{no}"),
        })
    info["nics"] = nics

    return info


# ── 印出結果 ──────────────────────────────────────────────────────────────────

def _fmt_gb(gb: float) -> str:
    return f"{gb/1024:.1f} TB" if gb >= 1024 else f"{gb:.1f} GB"


def print_system_info(name: str, info: dict):
    u = info["uptime"]
    uptime_str = f"{u['day']}d {u['hour']}h {u['min']}m {u['sec']}s"

    print(f"\n{'='*60}")
    print(f"  Server        : {name}")
    print(f"  Name          : {info['server_name']}")
    print(f"  Serial        : {info['serial_number']}")
    print(f"  Uptime        : {uptime_str}")
    print(f"  CPU Usage     : {info['cpu_usage']} %")

    if info["total_memory"]:
        used_mem = info["total_memory"] - info["free_memory"]
        mem_pct  = round(used_mem / info["total_memory"] * 100, 1)
        print(f"  Memory        : {used_mem} / {info['total_memory']} MB ({mem_pct}%)")
    else:
        print(f"  Memory        : N/A")

    print(f"  CPU Temp      : {info['cpu_tempc']} °C")
    print(f"  System Temp   : {info['sys_tempc']} °C")
    print(f"  Disk count    : HDD={info['disk_num']}  SSD={info['ssd_num']}  M.2={info['m2_num']}")

    if info.get("disk_usage"):
        print(f"  Disk Usage    :")
        for d in info["disk_usage"]:
            bar_len = 20
            filled  = round(d["percent"] / 100 * bar_len)
            bar     = "█" * filled + "░" * (bar_len - filled)
            print(f"    {d['name']:<10} [{bar}] {d['percent']:5.1f}%  "
                  f"{_fmt_gb(d['used_gb'])} / {_fmt_gb(d['total_gb'])}")

    if info["disk_temps"]:
        temps = "  ".join(f"Disk{d['no']}={d['tempc']}°C" for d in info["disk_temps"])
        print(f"  Disk Temps    : {temps}")

    if info["fans"]:
        rpms = "  ".join(f"Fan{f['no']}={f['rpm']} RPM" for f in info["fans"])
        print(f"  Fans          : {rpms}")

    if info["nics"]:
        print(f"  NICs ({info['nic_cnt']}):")
        for n in info["nics"]:
            print(f"    eth{n['no']}  {n['status']}  MAC={n['mac']}  RX={n['rx_packet']}  TX={n['tx_packet']}")


# ── 主程式 ────────────────────────────────────────────────────────────────────

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

        sid = api.get_sid()
        if not sid:
            print("  -> Login failed, skip.")
            continue

        print(f"  -> SID: {sid}")

        info = get_system_info(api)
        if info:
            info["disk_usage"] = api.get_disk_usage()
            print_system_info(name, info)
        else:
            print("  -> Failed to retrieve system info.")


if __name__ == "__main__":
    main()
