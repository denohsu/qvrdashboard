# QVR Management Dashboard

即時監控 QNAP QVR Pro 伺服器與攝影機狀態的 Web Dashboard。

---

## 系統架構

```
QVRDashboard/
├── main.py            # FastAPI 後端主程式，提供 REST API
├── qvrapi.py          # QVR Pro API 封裝模組
├── serverlist.txt     # 伺服器設定檔
└── static/
    ├── index.html     # 前端頁面結構
    ├── styles.css     # 前端樣式
    └── app.js         # 前端邏輯（資料拉取、渲染、分頁）
```

### 運作流程

```
瀏覽器 (30秒自動更新)
    │
    ▼
GET /api/dashboard_data
    │
    ▼
main.py (FastAPI)
    │  ThreadPoolExecutor 並行查詢所有伺服器
    ├─► QVRApi.check_connection()   → HTTP 連線檢查 (timeout 3s)
    ├─► QVRApi.get_sid()            → 登入取得 Session ID
    └─► QVRApi.get_guid()           → 取得攝影機清單 (qvrpro/camera/list)
    │
    ▼
回傳 JSON { servers, alarms }
    │
    ▼
app.js 渲染
    ├─ 服務器主機清單與狀態 (Servers Overview) + 統計數字
    ├─ 服務器攝影機狀態 (Cameras Status)
    └─ 警報管理列表 (Alarm Management) — 最多 50 筆，每頁 10 筆
```

### API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/` | 前端頁面 |
| GET | `/api/dashboard_data` | 取得所有伺服器與攝影機狀態 |
| POST | `/api/camera_action` | 控制攝影機錄影（啟動 / 停止） |

---

## 伺服器設定 (`serverlist.txt`)

每台伺服器以空白行分隔，格式如下：

```
QVRServer_1 : <顯示名稱>
IP_ADDRESS  : <IP 位址>
PORT        : <Port，預設 8080>
USERNAME    : <登入帳號>
PASSWORD    : <Base64 編碼密碼>
```

**密碼編碼方式（PowerShell）：**

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your_password"))
```

---

## 環境需求

- Python 3.9 以上
- 相依套件：

```
fastapi
uvicorn
requests
pydantic
```

---

## 安裝與啟動

### 1. 安裝相依套件

```bash
pip install fastapi uvicorn requests pydantic
```

### 2. 設定伺服器清單

編輯 `serverlist.txt`，依格式填入各 QVR Pro 伺服器資訊。

### 3. 啟動服務

```bash
python main.py
```

服務啟動後開啟瀏覽器前往：

```
http://127.0.0.1:6666
```

> 若需對外開放，服務預設已監聽 `0.0.0.0:6666`，確認防火牆規則後可直接從其他裝置存取。

---

## 攝影機狀態說明

### Connection Status

| API 原始值 | 顯示 | 顏色 |
|-----------|------|------|
| `NVR_CAM_CONNECTED` | On Line | 綠色 |
| `NVR_CAM_CONNECTING` | On Line | 綠色 |
| `NVR_CAM_CONNECT_IDLE` | IDLE | 灰色 |
| `NVR_CAM_DISCONNECTED` | Off Line | 紅色 |

### Recording Status

| API 原始值 | 顯示 | 顏色 |
|-----------|------|------|
| `RECORDING` | Recording | 綠色 |
| `NOT_RECORDING` | Not Recording | 紅色 |

---

## 警報規則

攝影機狀態為以下任一時，自動加入警報列表：

- `NVR_CAM_CONNECT_IDLE`（顯示為灰色 IDLE）
- `NVR_CAM_DISCONNECTED`（顯示為紅色 Off Line）

警報列表最多保留 **50 筆**，最新資料顯示於第一筆，每頁顯示 **10 筆**。
