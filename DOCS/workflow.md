# QVR Dashboard — API 功能說明文件

> 本文件說明 QVR Dashboard 系統中各功能所使用的 API 呼叫方式，分為三層：
> **QNAP 原廠 CGI API**（qvrapi.py 向 NAS 發送的請求）、
> **後端 FastAPI Endpoint**（main.py 提供給前端的 REST API）、
> **前端呼叫**（app.js 透過 fetch 呼叫的後端 API）。

---

## 目錄

1. [驗證與 SID 管理](#1-驗證與-sid-管理)
2. [取得攝影機清單](#2-取得攝影機清單)
3. [儀表板資料彙整](#3-儀表板資料彙整)
4. [系統狀態（System Info）](#4-系統狀態-system-info)
5. [磁碟使用量（Disk Usage）](#5-磁碟使用量-disk-usage)
6. [儲存池資訊（Pool Info）](#6-儲存池資訊-pool-info)
7. [硬碟 SMART 狀態](#7-硬碟-smart-狀態)
8. [記憶體使用狀況](#8-記憶體使用狀況)
9. [攝影機錄影控制](#9-攝影機錄影控制)
10. [伺服器設定管理（CRUD）](#10-伺服器設定管理-crud)
11. [歷史警報紀錄](#11-歷史警報紀錄)
12. [連線狀態檢查](#12-連線狀態檢查)
13. [HTTP Share Link 相關](#13-http-share-link-相關)

---

## 1. 驗證與 SID 管理

### 說明
QNAP NAS 使用 Session ID（SID）作為所有 API 的身份憑證。`QVRApi` 會優先嘗試 renew 已快取的 SID，若失效才重新登入。SID 持久化存放於 `sid_cache.json`，以 `ip:port:username` 為 key。

### QNAP CGI API — 取得 SID（登入）

```
GET /cgi-bin/authLogin.cgi
```

| 參數 | 說明 |
|------|------|
| `user` | 帳號名稱 |
| `serviceKey` | 固定為 `1` |
| `pwd` | Base64 編碼後的密碼 |

**回應格式：** XML，解析 `<authSid><![CDATA[...]]></authSid>` 取得 SID。

### QNAP CGI API — Renew SID（續用）

```
GET /cgi-bin/authLogin.cgi?sid={sid}
```

驗證快取 SID 是否仍有效，解析回應中的 `<authPassed><![CDATA[1]]></authPassed>`。

### 流程圖

```
get_sid()
  ├─ 有快取 SID → renew_sid() → 成功 → 直接使用
  │                           → 失效 → 重新登入 (authLogin.cgi?user=&pwd=)
  └─ 無快取 SID → 直接登入
                  → 成功 → 寫入 sid_cache.json
                  → 失敗 → 回傳 None
```

---

## 2. 取得攝影機清單

### 說明
取得該 NAS 上所有攝影機的基本資訊（名稱、狀態、錄影狀態、品牌、型號、解析度等）。

### QNAP CGI API

```
GET /{qvr_prefix}/camera/list?ver=1.1.0&sid={sid}
```

- `qvr_prefix`：自動從 `/qvrentry` 取得（`qvrpro` 或 `qvrelite`）。

**回應格式：** JSON
```json
{
  "total_channel_num": 16,
  "datas": [
    {
      "guid": "...",
      "name": "Camera 01",
      "channel_index": 1,
      "status": "NVR_CAM_CONNECTED",
      "rec_state": "RECORDING",
      "normal_rec_days": 7,
      "brand": "Hikvision",
      "model": "DS-2CD2143G2-I",
      "video_codec_setting": "H.264",
      "video_resolution_setting": "2560x1440",
      "frame_rate_setting": "15"
    }
  ]
}
```

### Python 方法
```python
api.get_guid()  # 回傳整個 JSON dict 或 None
```

---

## 3. 儀表板資料彙整

### 說明
前端每 30 秒輪詢一次，後端以多執行緒並行向所有 NAS 取得資料後彙整回傳。

### 後端 FastAPI Endpoint

```
GET /api/dashboard_data
```

**回應格式：** JSON
```json
{
  "timestamp": "2026-05-15 10:00:00",
  "servers": [
    {
      "name": "IEI29-QVR-01",
      "ip_address": "10.10.18.2",
      "qvr_prefix": "qvrpro",
      "status": "Online",
      "camera_count": 16,
      "cameras": [...],
      "disk_usage": [...],
      "pool_info": [...],
      "disk_smart": [
        {
          "id": "0",
          "model": "TVS-2472XU-RP",
          "total_bays": 24,
          "warnings": [],
          "errors": [{"hd_no": "0000:0009", "slot": 9, "hd_smart": "2", "label": "異常"}]
        },
        {
          "id": "1",
          "model": "TL-R1620Sep-RP",
          "total_bays": 16,
          "warnings": [],
          "errors": []
        }
      ]
    }
  ],
  "alarms": [...],
  "server_alarms": [...]
}
```

### 前端呼叫（app.js）

```javascript
const response = await fetch('/api/dashboard_data');
const data = await response.json();
```

### 後端彙整流程

```
_fetch_server_data(name, api, now_str)
  1. check_connection()  → 失敗 → 標記 Offline，記錄 server_alarm
  2. get_sid()           → 失敗 → 標記 Auth Failed，記錄 server_alarm
  3. get_guid()          → 失敗 → 標記 Service Error，記錄 server_alarm
  4. get_disk_usage()    → chartReq.cgi，fallback 顯示用
  5. get_pool_info()     → disk_manage.cgi，優先顯示
  6. get_disk_smart()    → disk_manage.cgi，Enclosure 硬碟健康狀態
  7. 遍歷攝影機清單 → 偵測斷線攝影機 → 記錄 cam_alarm
```

多台伺服器以 `ThreadPoolExecutor` 並行執行，結果依 `serverlist.txt` 順序排列。

---

## 4. 系統狀態 (System Info)

### 說明
點擊伺服器卡片上的「**系統狀態**」按鈕，即時查詢該台 NAS 的 CPU、溫度、運行時間、記憶體等資訊。同時包含 Storage Pool、磁碟 SMART 資訊（含 Enclosure 擴充主機）。

### 後端 FastAPI Endpoint

```
GET /api/system_info/{server_name}
```

**回應格式：** JSON
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
  "memory": { "total": 16777216, "used": 8192000, "free": 8585216, "pct": 48.8 },
  "disk_usage": [...],
  "pool_info": [...],
  "disk_smart": [...]
}
```

> `memory` 欄位單位為 **KB**，前端 `fmtKB()` 自動換算顯示單位（KB / MB / GB / TB / PB）。

### 前端呼叫（app.js）

```javascript
const res = await fetch(`/api/system_info/${encodeURIComponent(serverName)}`);
const data = await res.json();
```

### QNAP CGI API — 系統資訊

```
GET /cgi-bin/management/manaRequest.cgi?subfunc=sysinfo&count={timestamp}&sid={sid}
```

**回應格式：** XML（以 regex 解析各標籤）

主要擷取欄位：`server_name`, `serial_number`, `uptime_day/hour/min/sec`, `cpu_usage`, `cpu_tempc`, `sys_tempc`, `disk_num`, `ssd_disk_num`, `m2_disk_num`

> `cpu_usage` 欄位值已含 `%`，解析時需 `.replace("%", "").strip()` 避免重複顯示。

---

## 5. 磁碟使用量 (Disk Usage)

### 說明
查詢 System、DataVol1～DataVol3 各分區的總容量、已使用、可用空間（以 GB 為單位）。當無 Storage Pool 資料時作為 fallback 顯示。

### QNAP CGI API

```
GET /cgi-bin/management/chartReq.cgi
    ?chart_func=disk_usage
    &count={unix_timestamp}
    &disk_select={System|DataVol1|DataVol2|DataVol3}
    &sid={sid}
```

**回應格式：** XML，解析 `<total_size>` 與 `<free_size>`（單位：bytes）。

### Python 方法
```python
api.get_disk_usage()
# 回傳：[{"name": "System", "total_gb": 50.0, "used_gb": 20.3, "free_gb": 29.7, "percent": 40.6}, ...]
```

---

## 6. 儲存池資訊 (Pool Info)

### 說明
查詢硬碟儲存池（RAID Pool）的容量配置狀況，優先於 Disk Usage 顯示。逐一嘗試 Pool ID 1～15，直到無資料為止。

### QNAP CGI API

```
GET /cgi-bin/disk/disk_manage.cgi
    ?func=extra_get
    &store=poolInfo
    &poolID={1~15}
    &Pool_Info=1
    &sid={sid}
```

**回應格式：** XML，解析：
- `<pool_capacity>`：總容量（如 `261.74 TB`）
- `<pool_allocated>`：已分配容量
- `<pool_freesize>`：可用容量

### Python 方法
```python
api.get_pool_info()
# 回傳：[{"pool_id": 1, "capacity": "261.74 TB", "allocated": "200.00 TB", "freesize": "61.74 TB", "percent": 76.4}, ...]
```

---

## 7. 硬碟 SMART 狀態

### 說明
查詢所有實體硬碟的健康狀態，依 Enclosure 分組回傳。`hd_smart` 含義：`0` = 正常、`1` = 警告、`2` = 異常。

- **Host（ID=0）**：主機本體硬碟槽
- **External（ID≥1）**：擴充主機（如 JBOD 擴充盒），只要 `total_bays > 0` 即顯示

### QNAP CGI API

```
GET /cgi-bin/disk/disk_manage.cgi?func=get_all&sid={sid}
```

**回應結構：** XML，頂層包含一個或多個 `<Enclosure_info>`（部分韌體拼字為 `<Ecnlosure_info>`）區塊：

```xml
<Enclosure_info>
  <enclosureID>0</enclosureID>
  <enclModel>TVS-2472XU-RP</enclModel>
  <enclosureSlot>24</enclosureSlot>
  <Disk_Info>
    <row>
      <hd_no>0000:0009</hd_no>
      <hd_smart>2</hd_smart>
      <!-- 其他欄位 -->
    </row>
    <!-- 更多 row -->
  </Disk_Info>
</Enclosure_info>
<Enclosure_info>
  <enclosureID>1</enclosureID>
  <enclModel>TL-R1620Sep-RP</enclModel>
  <enclosureSlot>16</enclosureSlot>
  <Disk_Info>
    <!-- 正常磁碟 rows -->
  </Disk_Info>
</Enclosure_info>
```

### Python 方法

```python
api.get_disk_smart()
```

**回傳格式：** Enclosure 物件陣列

```python
[
    {
        "id":         "0",                 # enclosureID（字串）
        "model":      "TVS-2472XU-RP",     # enclModel
        "total_bays": 24,                  # enclosureSlot（整數）
        "warnings": [                      # hd_smart == "1"
            {"hd_no": "0000:0003", "slot": 3, "hd_smart": "1", "label": "警告"}
        ],
        "errors": [                        # hd_smart == "2"
            {"hd_no": "0000:0009", "slot": 9, "hd_smart": "2", "label": "異常"}
        ]
    },
    {
        "id":         "1",
        "model":      "TL-R1620Sep-RP",
        "total_bays": 16,
        "warnings":   [],
        "errors":     []
    }
]
```

### 前端顯示邏輯（app.js）

```
disk_smart 陣列
  ├─ alertEnclosures  = 有 warnings 或 errors 的 enclosure → 紅色警示區塊
  └─ healthyExternals = External(ID>0) 且 total_bays>0 且無問題 → 白色擴充主機區塊
```

| 條件 | Server Card 顯示 | 邊框效果 |
|------|-----------------|---------|
| 任何 enclosure 有問題 | 「硬碟狀態警示」紅色區塊 | 黃色邊框閃爍 |
| External 健康（bays>0） | 「擴充主機」白色區塊 | 無閃爍 |
| 伺服器離線 | 無磁碟資訊 | 紅色邊框閃爍 |

標頭格式：
- `Host - TVS-2472XU-RP · 24 Bay`
- `External 1 - TL-R1620Sep-RP · 16 Bay`

---

## 8. 記憶體使用狀況

### 說明
取得系統記憶體的總量、已用量、可用量及使用百分比。

### QNAP CGI API

```
GET /cgi-bin/management/manaRequest.cgi?subfunc=sysmonitor&sys_memory_use=1&sid={sid}
```

**回應格式：** XML，解析 `<mem_total>`, `<mem_used>`, `<mem_free>`（單位：**KB**）。

### Python 方法
```python
api.get_memory_info()
# 回傳：{"total": 16777216, "used": 8192000, "free": 8585216, "pct": 48.8}
# 注意：單位為 KB
```

### 前端換算（fmtKB）

```javascript
const fmtKB = kb => {
    const G = 1024, M = G * 1024, T = M * 1024, P = T * 1024;
    if (kb >= P) return (kb / P).toFixed(2) + ' PB';
    if (kb >= T) return (kb / T).toFixed(2) + ' TB';
    if (kb >= M) return (kb / M).toFixed(1) + ' GB';
    if (kb >= G) return (kb / G).toFixed(0) + ' MB';
    return kb.toFixed(0) + ' KB';
};
```

---

## 9. 攝影機錄影控制

### 說明
提供手動啟動或停止指定攝影機錄影的功能。

### 後端 FastAPI Endpoint

```
POST /api/camera_action
Content-Type: application/json

{
  "server_name": "IEI29-QVR-01",
  "camera_guid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "action": "start_rec"  // 或 "stop_rec"
}
```

**回應格式：** JSON
```json
{ "success": true }
```

### 前端呼叫（app.js）

```javascript
const response = await fetch('/api/camera_action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ server_name: serverName, camera_guid: cameraGuid, action: action })
});
```

### QNAP CGI API — 啟動錄影

```
PUT /{qvr_prefix}/camera/mrec/{camera_guid}/start?ver=1.1.0&sid={sid}
```

### QNAP CGI API — 停止錄影

```
PUT /{qvr_prefix}/camera/mrec/{camera_guid}/stop?ver=1.1.0&sid={sid}
```

### Python 方法
```python
api.start_recording(camera_guid)  # → bool
api.stop_recording(camera_guid)   # → bool
```

---

## 10. 伺服器設定管理 (CRUD)

### 說明
管理 `serverlist.txt` 中的 NAS 伺服器設定。前端傳入明碼密碼，後端自動以 Base64 編碼後存檔。

### 取得所有伺服器設定

```
GET /api/server_configs
```

**回應：** 伺服器清單（密碼以明碼回傳，供表單填充）

### 新增伺服器

```
POST /api/server_configs
Content-Type: application/json

{
  "name": "Server A",
  "ip_address": "192.168.1.10",
  "port": 8080,
  "username": "admin",
  "password": "plaintext_password"
}
```

### 修改伺服器

```
PUT /api/server_configs/{server_name}
Content-Type: application/json

{ "name": "...", "ip_address": "...", "port": 8080, "username": "...", "password": "..." }
```

### 刪除伺服器

```
DELETE /api/server_configs/{server_name}
```

### 前端呼叫（app.js）

```javascript
// 新增
await fetch('/api/server_configs', { method: 'POST', headers: {...}, body: JSON.stringify(payload) });

// 修改
await fetch(`/api/server_configs/${encodeURIComponent(serverName)}`, { method: 'PUT', ... });

// 刪除
await fetch(`/api/server_configs/${encodeURIComponent(serverName)}`, { method: 'DELETE' });
```

---

## 11. 歷史警報紀錄

### 說明
讀取儲存在 `logs/` 目錄下的輪轉 log 檔案，最多保留 14 天。支援攝影機警報與伺服器警報兩種類型。

### 後端 FastAPI Endpoint

```
GET /api/alarm_logs?type=camera   # 攝影機警報（預設）
GET /api/alarm_logs?type=server   # 伺服器連線警報
```

**回應格式：** JSON
```json
{
  "logs": [
    "2026-05-15 10:00:00 - CAMERA ALARM: IEI29-QVR-01 - Camera 01 (#1) is NVR_CAM_DISCONNECTED",
    "..."
  ]
}
```

> Log 順序為最新優先（newest first）。

### 前端呼叫（app.js）

```javascript
const response = await fetch(`/api/alarm_logs?type=${type}`);  // type = 'camera' or 'server'
const data = await response.json();
```

### Log 檔案位置

| 類型 | 檔案路徑 |
|------|----------|
| 攝影機警報 | `logs/camera_alarms.log`（及輪轉備份） |
| 伺服器警報 | `logs/server_alarms.log`（及輪轉備份） |

---

## 12. 連線狀態檢查

### 說明
在執行任何 QNAP API 之前，先以簡單 HTTP 請求確認伺服器是否在線（3 秒 timeout）。

### QNAP HTTP 連線測試

```
GET http://{ip_address}:{port}/
Timeout: 3 秒
```

任何 HTTP 回應（含 404/401/403）均視為在線；連線拒絕或逾時則視為 Offline。

### Python 方法
```python
api.check_connection()  # → bool
```

### qvrentry 前綴偵測

```
GET http://{ip_address}:{port}/qvrentry
```

解析 `fw_web_ui_prefix` 欄位，自動判斷使用 `qvrpro`（QVR Pro）或 `qvrelite`（QVR Elite）作為 API 路由前綴。

---

## 13. HTTP Share Link 相關

### 說明
查詢或管理攝影機的 HTTP 串流分享連結（此功能目前於 `qvrapi.py` 中已實作但前端尚未整合）。

### 取得全部攝影機分享連結狀態

```
GET /{qvr_prefix}/apis/camera_status.cgi?act=get_all_status&sid={sid}
```

```python
api.get_all_http_share_link_status()  # → dict
```

### 查詢單一攝影機分享連結

```
GET /{qvr_prefix}/apis/sharelink_settings.cgi?act=show_share_status&guid={camera_guid}&sid={sid}
```

```python
api.check_http_share_link_by_guid(camera_guid)  # → dict
```

### 啟用分享連結

```
POST /{qvr_prefix}/apis/sharelink_settings.cgi?act=enable&sid={sid}
Content-Type: application/json

{
  "guid": "...",
  "stream_id": 1,
  "enable_vcode": false,
  "vcode": "",
  "refresh": 0
}
```

```python
api.enable_share_link(camera_guid, stream_id=1, enable_vcode=False, vcode="", refresh=0)  # → dict
```

---

## 附錄：API 彙整總覽

| 功能 | 類型 | 方法 | 路徑 |
|------|------|------|------|
| 登入取得 SID | QNAP CGI | GET | `/cgi-bin/authLogin.cgi` |
| Renew SID | QNAP CGI | GET | `/cgi-bin/authLogin.cgi` |
| 偵測 QVR 前綴 | QNAP REST | GET | `/qvrentry` |
| 取得攝影機清單 | QNAP REST | GET | `/{prefix}/camera/list` |
| 啟動錄影 | QNAP REST | PUT | `/{prefix}/camera/mrec/{guid}/start` |
| 停止錄影 | QNAP REST | PUT | `/{prefix}/camera/mrec/{guid}/stop` |
| 系統資訊 | QNAP CGI | GET | `/cgi-bin/management/manaRequest.cgi?subfunc=sysinfo` |
| 記憶體資訊 | QNAP CGI | GET | `/cgi-bin/management/manaRequest.cgi?subfunc=sysmonitor` |
| 磁碟使用量 | QNAP CGI | GET | `/cgi-bin/management/chartReq.cgi?chart_func=disk_usage` |
| 硬碟 SMART | QNAP CGI | GET | `/cgi-bin/disk/disk_manage.cgi?func=get_all` |
| 儲存池資訊 | QNAP CGI | GET | `/cgi-bin/disk/disk_manage.cgi?func=extra_get&store=poolInfo` |
| 分享連結狀態 | QNAP CGI | GET | `/{prefix}/apis/camera_status.cgi` |
| 分享連結查詢 | QNAP CGI | GET | `/{prefix}/apis/sharelink_settings.cgi` |
| 分享連結啟用 | QNAP CGI | POST | `/{prefix}/apis/sharelink_settings.cgi` |
| 儀表板資料 | FastAPI | GET | `/api/dashboard_data` |
| 攝影機控制 | FastAPI | POST | `/api/camera_action` |
| 系統狀態 | FastAPI | GET | `/api/system_info/{server_name}` |
| 取得伺服器設定 | FastAPI | GET | `/api/server_configs` |
| 新增伺服器 | FastAPI | POST | `/api/server_configs` |
| 修改伺服器 | FastAPI | PUT | `/api/server_configs/{server_name}` |
| 刪除伺服器 | FastAPI | DELETE | `/api/server_configs/{server_name}` |
| 歷史警報紀錄 | FastAPI | GET | `/api/alarm_logs` |
