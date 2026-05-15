# QVR Management Dashboard

即時監控 QNAP QVR Pro / QVR Elite 伺服器與攝影機狀態的 Web Dashboard。

---

## 功能特色

| 功能 | 說明 |
|------|------|
| 多台伺服器監控 | 並行輪詢，30 秒自動更新 |
| 攝影機狀態 | 連線狀態、錄影狀態、錄影天數統計 |
| 儲存空間顯示 | Storage Pool（優先）/ Disk Usage（fallback） |
| 硬碟 SMART 監控 | 依 Enclosure 分組，區分警告(1) / 異常(2)，黃色邊框閃爍 |
| 擴充主機顯示 | 自動識別 External Enclosure（ID > 0），顯示型號與 Bay 數 |
| 系統狀態 Modal | CPU、溫度、Uptime、記憶體（自動換算單位）、硬碟資訊 |
| 警報記錄 | 伺服器連線警報 + 攝影機斷線警報，14 天輪轉 Log |
| 伺服器管理 | 前端新增 / 編輯 / 刪除伺服器設定，自動 Base64 密碼編碼 |
| SID 快取 | 登入 Session 持久化於 `sid_cache.json`，優先 renew 避免重複登入 |
| 自動偵測版本 | 透過 `/qvrentry` 自動判斷 QVR Pro / QVR Elite API 前綴 |

---

## 系統架構

```
QVRDashboard/
├── main.py            # FastAPI 後端主程式，提供 REST API
├── qvrapi.py          # QNAP QVR CGI/REST API 封裝模組
├── serverlist.txt     # 伺服器設定檔（Base64 密碼）
├── sid_cache.json     # SID 快取（ip:port:username → sid）
├── logs/              # 警報歷史紀錄
│   ├── server_alarms.log      # 伺服器連線警報（14 天輪轉）
│   └── camera_alarms.log      # 攝影機斷線警報（14 天輪轉）
├── static/
│   ├── index.html     # 前端頁面結構
│   ├── styles.css     # 前端樣式（Glass UI）
│   ├── app.js         # 前端邏輯（fetch / 渲染 / 分頁）
│   └── v3_IEI_Logo.svg
├── DOCS/
│   ├── workflow.md    # API 功能說明（CGI / FastAPI / JS 三層）
│   └── api_spec.md    # REST API 端點規格
└── scratch/           # 開發測試腳本
    ├── System_information.py
    ├── System_Memory.py
    ├── test_disk_usage.py
    └── run_test.py
```

### 資料流程

```
瀏覽器（每 30 秒自動更新）
    │
    ▼
GET /api/dashboard_data
    │
    ▼
main.py  ThreadPoolExecutor 並行查詢所有伺服器
    ├─► check_connection()   HTTP 連線檢查（timeout 3s）
    ├─► get_sid()            SID renew → 登入，寫入 sid_cache.json
    ├─► get_guid()           攝影機清單（{prefix}/camera/list）
    ├─► get_disk_usage()     磁碟分區使用量
    ├─► get_pool_info()      Storage Pool 資訊（優先顯示）
    └─► get_disk_smart()     Enclosure 硬碟 SMART 健康狀態
    │
    ▼
回傳 JSON { timestamp, servers[], alarms[], server_alarms[] }
    │
    ▼
app.js 渲染
    ├─ 服務器主機清單與狀態（含 Storage、SMART 警示、擴充主機）
    ├─ 攝影機狀態列表（可展開 / 收合）
    ├─ 主機連線警報表（分頁）
    └─ 攝影機警報管理表（分頁）
```

---

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/` | 前端頁面 |
| GET | `/api/dashboard_data` | 所有伺服器與攝影機狀態 |
| GET | `/api/system_info/{server_name}` | 即時系統狀態（CPU / 記憶體 / 硬碟）|
| POST | `/api/camera_action` | 控制攝影機錄影（啟動 / 停止）|
| GET | `/api/server_configs` | 取得伺服器設定清單 |
| POST | `/api/server_configs` | 新增伺服器設定 |
| PUT | `/api/server_configs/{server_name}` | 修改指定伺服器設定 |
| DELETE | `/api/server_configs/{server_name}` | 刪除指定伺服器設定 |
| GET | `/api/alarm_logs?type=camera\|server` | 歷史警報紀錄（最多 14 天）|

---

## 伺服器設定 (`serverlist.txt`)

每台伺服器以空白行分隔：

```
QVRServer_1 : <顯示名稱>
IP_ADDRESS  : <IP 位址>
PORT        : <Port，預設 8080>
USERNAME    : <登入帳號>
PASSWORD    : <Base64 編碼密碼>
```

**密碼 Base64 編碼（PowerShell）：**

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your_password"))
```

**密碼 Base64 編碼（Python）：**

```python
import base64
base64.b64encode("your_password".encode()).decode()
```

---

## 環境需求

- Python 3.10 以上（使用 `X | Y` 型別提示語法）
- 相依套件：

```
fastapi
uvicorn
requests
pydantic
```

---

## 安裝與啟動

```bash
# 1. 安裝相依套件
pip install fastapi uvicorn requests pydantic

# 2. 設定伺服器清單
# 編輯 serverlist.txt，依格式填入各 QVR 伺服器資訊

# 3. 啟動服務
python main.py
```

服務預設監聽 `0.0.0.0:9999`，開啟瀏覽器前往：

```
http://127.0.0.1:9999
```

---

## 攝影機狀態說明

### 連線狀態

| API 原始值 | 顯示 | 顏色 |
|-----------|------|------|
| `NVR_CAM_CONNECTED` | On Line | 綠色 |
| `NVR_CAM_CONNECTING` | Off Line | 紅色 |
| `NVR_CAM_CONNECT_IDLE` | IDLE | 灰色 |
| `NVR_CAM_DISCONNECTED` | Off Line | 紅色 |

### 錄影狀態

| API 原始值 | 顯示 | 顏色 |
|-----------|------|------|
| `RECORDING` | Recording | 綠色 |
| `NOT_RECORDING` | Not Recording | 紅色 |

---

## 硬碟 SMART 狀態說明

`get_disk_smart()` 解析 `<Enclosure_info>`（或 `<Ecnlosure_info>`，韌體 typo）區塊：

| `hd_smart` 值 | 說明 | 顯示 |
|---|---|---|
| `0` | 正常 | 不顯示 |
| `1` | 警告 | 橘色 ⚠ |
| `2` | 異常 | 紅色 ✕ |

| Enclosure ID | 類型 | 標頭格式 |
|---|---|---|
| `0` | Host（主機本體） | `Host - 型號 · N Bay` |
| `1+` | External（擴充主機） | `External N - 型號 · N Bay` |

- 有任何 SMART 問題 → 伺服器卡片黃色邊框閃爍
- `total_bays == 0` 的 Enclosure（系統虛擬項目）自動跳過

---

## 警報規則

攝影機狀態為以下任一時，自動加入警報列表：

- `NVR_CAM_DISCONNECTED`（紅色 Off Line）
- `NVR_CAM_CONNECTING`（紅色 Off Line）

警報列表最多保留 **50 筆**，最新資料顯示於第一筆，每頁顯示 **10 筆**。
