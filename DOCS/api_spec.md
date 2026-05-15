# QVR Dashboard — REST API 規格

> 本文件列出 `main.py`（FastAPI）對外提供的所有 REST API 端點，包含請求格式、回應格式與欄位說明。

---

## 目錄

1. [GET /api/dashboard\_data](#1-get-apidashboard_data)
2. [GET /api/system\_info/{server\_name}](#2-get-apisystem_infoserver_name)
3. [POST /api/camera\_action](#3-post-apicamera_action)
4. [GET /api/server\_configs](#4-get-apiserver_configs)
5. [POST /api/server\_configs](#5-post-apiserver_configs)
6. [PUT /api/server\_configs/{server\_name}](#6-put-apiserver_configsserver_name)
7. [DELETE /api/server\_configs/{server\_name}](#7-delete-apiserver_configsserver_name)
8. [GET /api/alarm\_logs](#8-get-apialarm_logs)
9. [資料模型參考](#9-資料模型參考)

---

## 1. GET /api/dashboard_data

### 說明
並行查詢所有已設定伺服器，回傳完整儀表板狀態。前端每 30 秒呼叫一次。

### 請求
```
GET /api/dashboard_data
```

無參數。

### 回應

```json
{
  "timestamp": "2026-05-15 10:00:00",
  "servers": [ <ServerInfo>, ... ],
  "alarms": [ <CameraAlarm>, ... ],
  "server_alarms": [ <ServerAlarm>, ... ]
}
```

#### ServerInfo 物件

```json
{
  "name": "IEI29-QVR-01",
  "ip_address": "10.10.18.2",
  "qvr_prefix": "qvrpro",
  "status": "Online",
  "camera_count": 16,
  "cameras": [ <Camera>, ... ],
  "disk_usage": [ <DiskUsage>, ... ],
  "pool_info": [ <PoolInfo>, ... ],
  "disk_smart": [ <Enclosure>, ... ]
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| `status` | string | `Online` / `Offline` / `Auth Failed` / `Service Error` |
| `qvr_prefix` | string | `qvrpro` 或 `qvrelite`（自動偵測） |
| `disk_smart` | Enclosure[] | 硬碟 Enclosure 清單，見 [Enclosure 模型](#enclosure) |

#### Camera 物件

```json
{
  "channel_index": 1,
  "name": "Camera 01",
  "status": "NVR_CAM_CONNECTED",
  "rec_state": "RECORDING",
  "guid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "normal_rec_days": 7,
  "brand": "Hikvision",
  "model": "DS-2CD2143G2-I",
  "video_codec_setting": "H.264",
  "video_resolution_setting": "2560x1440",
  "frame_rate_setting": "15"
}
```

#### DiskUsage 物件

```json
{
  "name": "System",
  "total_gb": 50.0,
  "used_gb": 20.3,
  "free_gb": 29.7,
  "percent": 40.6
}
```

#### PoolInfo 物件

```json
{
  "pool_id": 1,
  "capacity": "261.74 TB",
  "allocated": "200.00 TB",
  "freesize": "61.74 TB",
  "percent": 76.4
}
```

#### CameraAlarm 物件

```json
{
  "server_name": "IEI29-QVR-01",
  "camera_index": 3,
  "camera_name": "Camera 03",
  "camera_status": "NVR_CAM_DISCONNECTED",
  "timestamp": "2026-05-15 10:00:00"
}
```

#### ServerAlarm 物件

```json
{
  "server_name": "IEI29-QVR-01",
  "ip_address": "10.10.18.2",
  "status": "Offline",
  "timestamp": "2026-05-15 10:00:00"
}
```

---

## 2. GET /api/system_info/{server_name}

### 說明
即時查詢指定伺服器的系統狀態（CPU、溫度、記憶體、硬碟、Storage Pool）。由前端「系統狀態」按鈕觸發。

### 請求
```
GET /api/system_info/{server_name}
```

| 路徑參數 | 說明 |
|----------|------|
| `server_name` | 伺服器顯示名稱（需 URL encode） |

### 回應（成功）

```json
{
  "success": true,
  "sysinfo": {
    "server_name": "TVS-2472XU-RP",
    "serial_number": "Q12A34567",
    "uptime_day": 10,
    "uptime_hour": 3,
    "uptime_min": 22,
    "uptime_sec": 5,
    "cpu_usage": "15",
    "cpu_tempc": "45",
    "sys_tempc": "38",
    "disk_num": 24,
    "ssd_num": 0,
    "m2_num": 0
  },
  "memory": {
    "total": 16777216,
    "used": 8192000,
    "free": 8585216,
    "pct": 48.8
  },
  "disk_usage": [ <DiskUsage>, ... ],
  "pool_info": [ <PoolInfo>, ... ],
  "disk_smart": [ <Enclosure>, ... ]
}
```

> `memory` 欄位單位為 **KB**，前端 `fmtKB()` 自動換算為 MB / GB / TB / PB。

### 回應（失敗）

```json
{ "success": false, "message": "Connection failed" }
```

---

## 3. POST /api/camera_action

### 說明
啟動或停止指定攝影機的手動錄影。

### 請求

```
POST /api/camera_action
Content-Type: application/json
```

```json
{
  "server_name": "IEI29-QVR-01",
  "camera_guid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "action": "start_rec"
}
```

| 欄位 | 說明 |
|------|------|
| `action` | `start_rec`（啟動錄影）或 `stop_rec`（停止錄影） |

### 回應

```json
{ "success": true }
```

---

## 4. GET /api/server_configs

### 說明
取得所有已設定伺服器的設定資料（密碼以明碼回傳，供前端表單填充）。

### 回應

```json
[
  {
    "name": "IEI29-QVR-01",
    "ip_address": "10.10.18.2",
    "port": 8080,
    "username": "qvrdashboard",
    "password": "plaintext_password"
  }
]
```

---

## 5. POST /api/server_configs

### 說明
新增一台伺服器設定，密碼由後端自動 Base64 編碼後寫入 `serverlist.txt`。

### 請求

```json
{
  "name": "New-Server",
  "ip_address": "192.168.1.100",
  "port": 8080,
  "username": "admin",
  "password": "plaintext_password"
}
```

### 回應

```json
{ "success": true }
// 或
{ "success": false, "message": "Server name already exists" }
```

---

## 6. PUT /api/server_configs/{server_name}

### 說明
修改指定伺服器設定。

### 請求

```
PUT /api/server_configs/{server_name}
Content-Type: application/json
```

請求 Body 格式同 [POST /api/server_configs](#5-post-apiserver_configs)。

### 回應

```json
{ "success": true }
// 或
{ "success": false, "message": "Server not found" }
```

---

## 7. DELETE /api/server_configs/{server_name}

### 說明
刪除指定伺服器設定並從 `serverlist.txt` 移除。

### 回應

```json
{ "success": true }
```

---

## 8. GET /api/alarm_logs

### 說明
讀取最多 14 天的歷史警報紀錄，最新優先排序。

### 請求

```
GET /api/alarm_logs?type=camera   # 攝影機警報（預設）
GET /api/alarm_logs?type=server   # 伺服器連線警報
```

### 回應

```json
{
  "logs": [
    "2026-05-15 10:00:00 - CAMERA ALARM: IEI29-QVR-01 - Camera 03 (#3) is NVR_CAM_DISCONNECTED",
    "2026-05-15 09:30:00 - SERVER ALARM: IEI29-QVR-02 (IP: 10.10.18.3) is Offline"
  ]
}
```

---

## 9. 資料模型參考

### Enclosure

`disk_smart` 欄位回傳的 Enclosure 陣列格式（`get_disk_smart()` 新結構）：

```json
[
  {
    "id": "0",
    "model": "TVS-2472XU-RP",
    "total_bays": 24,
    "warnings": [
      { "hd_no": "0000:0003", "slot": 3, "hd_smart": "1", "label": "警告" }
    ],
    "errors": [
      { "hd_no": "0000:0009", "slot": 9, "hd_smart": "2", "label": "異常" }
    ]
  },
  {
    "id": "1",
    "model": "TL-R1620Sep-RP",
    "total_bays": 16,
    "warnings": [],
    "errors": []
  }
]
```

| 欄位 | 說明 |
|------|------|
| `id` | Enclosure ID（`"0"` = Host 主機本體，`"1"`+ = External 擴充主機） |
| `model` | XML `<enclModel>` 標籤值（型號名稱） |
| `total_bays` | XML `<enclosureSlot>` 標籤值（總 Bay 數） |
| `warnings` | `hd_smart == "1"` 的硬碟清單 |
| `errors` | `hd_smart == "2"` 的硬碟清單 |

> Enclosure ID > 0 且 `total_bays > 0` 的擴充主機，即使無磁碟問題也會在 Server Card 顯示。  
> `total_bays == 0` 的 Enclosure（系統虛擬項目）自動過濾不顯示。

### DiskEntry（warnings / errors 內的元素）

```json
{
  "hd_no": "0000:0009",
  "slot": 9,
  "hd_smart": "2",
  "label": "異常"
}
```

| `hd_smart` | `label` |
|---|---|
| `"0"` | 正常（不出現在清單中） |
| `"1"` | 警告 |
| `"2"` | 異常 |

---

## 前端呼叫範例（app.js）

```javascript
// 儀表板資料
const data = await (await fetch('/api/dashboard_data')).json();

// 系統狀態
const info = await (await fetch(`/api/system_info/${encodeURIComponent(serverName)}`)).json();

// 歷史警報
const logs = await (await fetch('/api/alarm_logs?type=camera')).json();

// 新增伺服器
await fetch('/api/server_configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ip_address, port, username, password })
});
```
