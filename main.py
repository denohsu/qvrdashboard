import os
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from pydantic import BaseModel
import logging
from logging.handlers import TimedRotatingFileHandler

# 導入我們寫好的 qvrapi
from qvrapi import (load_servers_from_file, load_all_server_configs,
                    save_servers_to_file, encode_password, decode_password)

SERVERLIST_PATH = "serverlist.txt"

app = FastAPI(title="QVR Dashboard API")

# 確保 logs 資料夾存在
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 設定主機警報記錄器 (14天輪轉)
server_alarm_logger = logging.getLogger("ServerAlarmLogger")
server_alarm_logger.setLevel(logging.INFO)
if not server_alarm_logger.handlers:
    server_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "server_alarms.log"),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8"
    )
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    server_handler.setFormatter(formatter)
    server_alarm_logger.addHandler(server_handler)

# 設定攝影機警報記錄器 (14天輪轉)
camera_alarm_logger = logging.getLogger("CameraAlarmLogger")
camera_alarm_logger.setLevel(logging.INFO)
if not camera_alarm_logger.handlers:
    camera_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "camera_alarms.log"),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8"
    )
    camera_handler.setFormatter(formatter)
    camera_alarm_logger.addHandler(camera_handler)

def update_and_log_alarms(cam_alarms, server_alarms):
    # 直接記錄所有當前的警報 (每次 polling 都會記錄，讓歷史看得到持續狀態)
    for a in server_alarms:
        server_alarm_logger.info(f"SERVER ALARM: {a['server_name']} (IP: {a['ip_address']}) is {a['status']}")
        
    for a in cam_alarms:
        camera_alarm_logger.info(f"CAMERA ALARM: {a['server_name']} - {a['camera_name']} (#{a['camera_index']}) is {a['camera_status']}")

# 確保 static 資料夾存在
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# 掛載 static 資料夾以提供前端檔案
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard is building...</h1>"

def _fetch_server_data(name: str, api, now_str: str) -> tuple:
    """單一伺服器的資料擷取，回傳 (server_info, cam_alarms, server_alarm)，供並行執行使用。"""
    server_info = {
        "name": name,
        "ip_address": api.ip_address,
        "qvr_prefix": "qvrpro",
        "status": "Offline",
        "camera_count": 0,
        "cameras": [],
        "disk_usage": [],
        "pool_info": [],
        "disk_smart": [],
    }
    cam_alarms = []

    if not api.check_connection():
        server_alarm = {"server_name": name, "ip_address": api.ip_address,
                        "status": "Offline", "timestamp": now_str}
        return server_info, cam_alarms, server_alarm

    if not api.get_sid():  # get_sid 內部已處理 renew → 重登
        server_info["status"] = "Auth Failed"
        server_alarm = {"server_name": name, "ip_address": api.ip_address,
                        "status": "Auth Failed", "timestamp": now_str}
        return server_info, cam_alarms, server_alarm

    camera_data = api.get_guid()
    if camera_data is None:
        # SID 有效但攝影機清單 API 失敗，代表 QVR 服務異常
        server_info["status"] = "Service Error"
        server_alarm = {"server_name": name, "ip_address": api.ip_address,
                        "status": "Service Error", "timestamp": now_str}
        return server_info, cam_alarms, server_alarm

    server_info["status"] = "Online"
    server_info["qvr_prefix"] = api._qvr_prefix or "qvrpro"
    server_info["disk_usage"] = api.get_disk_usage()
    server_info["pool_info"]  = api.get_pool_info()
    server_info["disk_smart"] = api.get_disk_smart()

    cameras_raw = []
    if isinstance(camera_data, dict):
        cameras_raw = camera_data.get("datas", [])
        server_info["camera_count"] = camera_data.get("total_channel_num", len(cameras_raw))
    elif isinstance(camera_data, list):
        cameras_raw = camera_data
        server_info["camera_count"] = len(cameras_raw)

    for cam in cameras_raw:
        cam_status = cam.get("status", "UNKNOWN")
        cam_name = cam.get("name", "Unknown Camera")
        cam_index = cam.get("channel_index", -1)

        server_info["cameras"].append({
            "channel_index": cam_index,
            "name": cam_name,
            "status": cam_status,
            "rec_state": cam.get("rec_state", "UNKNOWN"),
            "guid": cam.get("guid", ""),
            "normal_rec_days": cam.get("normal_rec_days", 0),
            "brand": cam.get("brand", "Unknown"),
            "model": cam.get("model", "Unknown"),
            "video_codec_setting": cam.get("video_codec_setting", "Unknown"),
            "video_resolution_setting": cam.get("video_resolution_setting", "Unknown"),
            "frame_rate_setting": cam.get("frame_rate_setting", "Unknown")
        })

        _s = cam_status.upper()
        if "DISCONNECTED" in _s or _s == "NVR_CAM_CONNECTING":
            cam_alarms.append({
                "server_name": name,
                "camera_index": cam_index,
                "camera_name": cam_name,
                "camera_status": cam_status,
                "timestamp": now_str
            })

    return server_info, cam_alarms, None  # None 表示主機正常，無主機警報


@app.get("/api/dashboard_data")
def get_dashboard_data():
    """
    並行獲取所有伺服器與攝影機的狀態資料。
    """
    servers = load_servers_from_file("serverlist.txt")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results = {}
    with ThreadPoolExecutor(max_workers=len(servers) or 1) as executor:
        futures = {
            executor.submit(_fetch_server_data, name, api, now_str): name
            for name, api in servers.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()

    # 依原始設定檔順序排列
    server_list = []
    alarm_list = []
    server_alarm_list = []
    for name in servers:
        server_info, cam_alarms, server_alarm = results[name]
        server_list.append(server_info)
        alarm_list.extend(cam_alarms)
        if server_alarm:
            server_alarm_list.append(server_alarm)

    # 記錄警報至 LOG 檔案
    update_and_log_alarms(alarm_list, server_alarm_list)

    return {
        "timestamp": now_str,
        "servers": server_list,
        "alarms": alarm_list,
        "server_alarms": server_alarm_list
    }

class CameraAction(BaseModel):
    server_name: str
    camera_guid: str
    action: str

@app.post("/api/camera_action")
def do_camera_action(payload: CameraAction):
    """處理攝影機操作 (例如啟動或停止錄影)"""
    servers = load_servers_from_file("serverlist.txt")
    if payload.server_name not in servers:
        return {"success": False, "message": "Server not found"}
        
    api = servers[payload.server_name]
    if not api.check_connection() or not api.get_sid():
        return {"success": False, "message": "Failed to connect to server"}
        
    if payload.action == "start_rec":
        success = api.start_recording(payload.camera_guid)
        return {"success": success}
    elif payload.action == "stop_rec":
        success = api.stop_recording(payload.camera_guid)
        return {"success": success}
    else:
        return {"success": False, "message": "Invalid action"}

class ServerConfig(BaseModel):
    name: str
    ip_address: str
    port: int = 8080
    username: str
    password: str  # 前端傳入明碼，後端轉 Base64 後存檔


@app.get("/api/server_configs")
def get_server_configs():
    """取得所有伺服器設定（密碼解碼為明碼供前端顯示）"""
    configs = load_all_server_configs(SERVERLIST_PATH)
    return [
        {
            "name": c["name"],
            "ip_address": c["ip_address"],
            "port": c["port"],
            "username": c["username"],
            "password": decode_password(c["password_base64"]),
        }
        for c in configs
    ]


@app.post("/api/server_configs")
def add_server_config(payload: ServerConfig):
    """新增一台伺服器設定"""
    configs = load_all_server_configs(SERVERLIST_PATH)
    if any(c["name"] == payload.name for c in configs):
        return {"success": False, "message": "Server name already exists"}
    configs.append({
        "name": payload.name,
        "ip_address": payload.ip_address,
        "port": payload.port,
        "username": payload.username,
        "password_base64": encode_password(payload.password),
    })
    save_servers_to_file(SERVERLIST_PATH, configs)
    return {"success": True}


@app.put("/api/server_configs/{server_name}")
def update_server_config(server_name: str, payload: ServerConfig):
    """修改指定伺服器設定"""
    configs = load_all_server_configs(SERVERLIST_PATH)
    for cfg in configs:
        if cfg["name"] == server_name:
            cfg["name"] = payload.name
            cfg["ip_address"] = payload.ip_address
            cfg["port"] = payload.port
            cfg["username"] = payload.username
            cfg["password_base64"] = encode_password(payload.password)
            save_servers_to_file(SERVERLIST_PATH, configs)
            return {"success": True}
    return {"success": False, "message": "Server not found"}


@app.delete("/api/server_configs/{server_name}")
def delete_server_config(server_name: str):
    """刪除指定伺服器設定"""
    configs = load_all_server_configs(SERVERLIST_PATH)
    new_configs = [c for c in configs if c["name"] != server_name]
    if len(new_configs) == len(configs):
        return {"success": False, "message": "Server not found"}
    save_servers_to_file(SERVERLIST_PATH, new_configs)
    return {"success": True}


@app.get("/api/system_info/{server_name}")
def get_server_system_info(server_name: str):
    """取得指定伺服器的系統身分證資訊"""
    servers = load_servers_from_file(SERVERLIST_PATH)
    if server_name not in servers:
        return {"success": False, "message": "Server not found"}

    api = servers[server_name]
    if not api.check_connection():
        return {"success": False, "message": "Connection failed"}
    if not api.get_sid():
        return {"success": False, "message": "Auth failed"}

    return {
        "success":    True,
        "sysinfo":    api.get_system_info(),
        "memory":     api.get_memory_info(),
        "disk_usage": api.get_disk_usage(),
        "pool_info":  api.get_pool_info(),
        "disk_smart": api.get_disk_smart(),
    }


@app.get("/api/alarm_logs")
def get_alarm_logs(type: str = "camera"):
    """讀取最多 14 天的歷史警報紀錄"""
    import glob
    
    log_prefix = "camera_alarms.log" if type == "camera" else "server_alarms.log"
    log_files = glob.glob(os.path.join(LOGS_DIR, f"{log_prefix}*"))
    
    def sort_key(f):
        return f if f != os.path.join(LOGS_DIR, log_prefix) else "z" * 100
        
    log_files.sort(key=sort_key, reverse=True) # newest files first
    
    all_logs = []
    for fpath in log_files:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                    # 檔案內是由舊到新，所以將這個檔案的行反轉
                    lines.reverse()
                    all_logs.extend(lines)
            except Exception:
                pass
                
    return {"logs": all_logs}


if __name__ == "__main__":
    print("啟動 QVR Dashboard 伺服器... 請瀏覽 http://127.0.0.1:9999")
    uvicorn.run("main:app", host="0.0.0.0", port=9999, reload=True)
