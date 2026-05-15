import base64
import json
import os
import requests
import re
import urllib.parse
from typing import Optional, Dict, Any, List

# SID 快取檔路徑（與 qvrapi.py 同目錄）
_SID_CACHE_PATH = os.path.join(os.path.dirname(__file__), "sid_cache.json")


def _load_sid_cache() -> dict:
    if os.path.exists(_SID_CACHE_PATH):
        try:
            with open(_SID_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_sid_cache(cache: dict):
    try:
        with open(_SID_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[sid_cache] 寫入失敗: {e}")


class QVRApi:
    def __init__(self, ip_address: str, port: int, username: str, password_base64: str):
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password_base64
        self.base_url = f"http://{self.ip_address}:{self.port}"
        self._qvr_prefix = None
        self._cache_key = f"{ip_address}:{port}:{username}"

        # 從快取還原 SID（尚未驗證有效性，get_sid() 呼叫時才 renew）
        cache = _load_sid_cache()
        self.sid = cache.get(self._cache_key)

    def get_qvr_prefix(self) -> str:
        """從 /qvrentry 取得 fw_web_ui_prefix，自動適應 QVR Pro / QVR Elite"""
        if self._qvr_prefix is not None:
            return self._qvr_prefix
            
        try:
            url = f"{self.base_url}/qvrentry"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                prefix = data.get("fw_web_ui_prefix", "qvrpro")
                self._qvr_prefix = prefix.strip('/')
            else:
                self._qvr_prefix = "qvrpro"
        except Exception as e:
            print(f"Error getting qvrentry for {self.ip_address}: {e}")
            self._qvr_prefix = "qvrpro"
            
        return self._qvr_prefix

    def _get(self, endpoint: str, params: Dict[str, Any] = None) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        if params is None:
            params = {}
        if self.sid and 'sid' not in params:
            params['sid'] = self.sid
            
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response

    def _post(self, endpoint: str, data: Dict[str, Any] = None, json_data: Dict[str, Any] = None) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        params = {}
        if self.sid:
            params['sid'] = self.sid
            
        response = requests.post(url, params=params, data=data, json=json_data, timeout=10)
        response.raise_for_status()
        return response

    def _put(self, endpoint: str, params: Dict[str, Any] = None, data: Dict[str, Any] = None, json_data: Dict[str, Any] = None) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        if params is None:
            params = {}
        if self.sid and 'sid' not in params:
            params['sid'] = self.sid
            
        response = requests.put(url, params=params, data=data, json=json_data, timeout=10)
        response.raise_for_status()
        return response

    def get_sid(self) -> Optional[str]:
        """取得 SID：優先 renew 快取 SID，失效才重新登入，成功後存入快取。"""
        if self.sid and self.renew_sid():
            return self.sid

        params = {
            "user": self.username,
            "serviceKey": "1",
            "pwd": self.password
        }
        try:
            response = self._get("cgi-bin/authLogin.cgi", params=params)
            match = re.search(r'<authSid>\s*<!\[CDATA\[(.*?)\]\]>\s*</?authSid>', response.text, re.IGNORECASE)
            if match:
                self.sid = match.group(1)
                self._save_sid()
                return self.sid
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting SID: {e}")
            return None

    def _save_sid(self):
        """將目前 SID 寫入快取檔。"""
        cache = _load_sid_cache()
        if cache.get(self._cache_key) != self.sid:
            cache[self._cache_key] = self.sid
            _save_sid_cache(cache)
            print(f"[sid_cache] {self._cache_key} SID 已更新")

    def renew_sid(self) -> bool:
        """續用 SID 方式"""
        if not self.sid:
            print("No SID available to renew.")
            return False
            
        try:
            # _get 方法已設定會自動帶入 self.sid
            response = self._get("cgi-bin/authLogin.cgi")
            match = re.search(r'<authPassed>\s*<!\[CDATA\[(.*?)\]\]>\s*</?authPassed>', response.text, re.IGNORECASE)
            
            if match and match.group(1) == "1":
                return True
            else:
                self.sid = None # SID 已失效
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Error renewing SID: {e}")
            return False

    def check_connection(self) -> bool:
        """檢查伺服器連線狀態 (判斷伺服器是否在線且 HTTP 服務正常)"""
        try:
            # 僅測試與伺服器的基本 HTTP 連線，設定 3 秒 timeout
            response = requests.get(self.base_url, timeout=3)
            # 只要伺服器有回應 (即使是 404/401/403 等) 就代表機器活著
            return True
        except requests.exceptions.RequestException:
            return False

    def get_guid(self):
        """取得攝影機列表。成功回傳 dict/list；API 呼叫失敗回傳 None。"""
        if not self.sid:
            print("No SID available.")
            return None

        params = {"ver": "1.1.0"}
        try:
            response = self._get(f"{self.get_qvr_prefix()}/camera/list", params=params)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting camera list: {e}")
            return None
        except ValueError:
            print("Failed to parse JSON response.")
            return None

    def get_disk_usage(self) -> list:
        """取得各磁碟使用空間，回傳 list of dict (name, total_gb, used_gb, free_gb, percent)。"""
        if not self.sid:
            print(f"[disk_usage][{self.ip_address}] 無 SID，略過")
            return []

        import time
        import re
        import xml.etree.ElementTree as ET

        def _extract(text, tag):
            """從 XML 文字中用 regex 擷取 tag 的值（支援 CDATA 與純文字，忽略換行空白）。"""
            pattern = rf'<{tag}[^>]*>\s*(?:<!\[CDATA\[)?\s*([\d.]+)\s*(?:\]\]>)?\s*</{tag}>'
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else None

        disks = []
        for disk_select in ["System", "DataVol1", "DataVol2", "DataVol3"]:
            params = {
                "chart_func": "disk_usage",
                "count": int(time.time()),
                "disk_select": disk_select,
            }
            try:
                resp = self._get("cgi-bin/management/chartReq.cgi", params=params)
                raw = resp.text

                print(f"[disk_usage][{self.ip_address}][{disk_select}] HTTP {resp.status_code} len={len(raw)}")
                print(f"[disk_usage][{self.ip_address}][{disk_select}] RAW >>>\n{raw}\n<<<")

                # chartReq.cgi for disk_usage might not return authPassed, so we rely on total_size presence

                total_str = _extract(raw, "total_size")
                free_str  = _extract(raw, "free_size")

                if not total_str:
                    all_tags = re.findall(r'<(\w+)[^>]*>\s*(?:<!\[CDATA\[)?\s*([\d.]+)\s*(?:\]\]>)?\s*</\1>', raw, re.DOTALL)
                    print(f"[disk_usage][{self.ip_address}][{disk_select}] 找不到 total_size，數字型 tag: {all_tags[:20]}")
                    continue

                total_bytes = float(total_str)
                free_bytes  = float(free_str) if free_str else 0.0

                if total_bytes <= 0:
                    continue

                GB = 1024 ** 3
                total_gb = total_bytes / GB
                free_gb  = free_bytes  / GB
                used_gb  = total_gb - free_gb

                print(f"[disk_usage][{self.ip_address}][{disk_select}] total={total_gb:.1f}GB used={used_gb:.1f}GB free={free_gb:.1f}GB")

                disks.append({
                    "name":      disk_select,
                    "total_gb":  round(total_gb, 1),
                    "used_gb":   round(used_gb,  1),
                    "free_gb":   round(free_gb,  1),
                    "percent":   round(used_gb / total_gb * 100, 1),
                })
            except Exception as e:
                print(f"[disk_usage][{self.ip_address}][{disk_select}] exception: {e}")
        return disks

    def get_disk_smart(self) -> list:
        """
        解析 disk_manage.cgi?func=get_all 的 <Ecnlosure_info> 區塊。
        回傳格式：
        [{"id": "0", "model": "...", "total_bays": 24,
          "warnings": [{"hd_no": "...", "slot": N, "hd_smart": "1", "label": "警告"}],
          "errors":   [{"hd_no": "...", "slot": N, "hd_smart": "2", "label": "異常"}]}]
        """
        if not self.sid:
            return []

        import re as _re

        def _x(text, tag):
            m = _re.search(
                rf'<{_re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{_re.escape(tag)}>',
                text, _re.IGNORECASE | _re.DOTALL)
            return m.group(1).strip() if m else None

        SMART_LABEL = {"0": "正常", "1": "警告", "2": "異常"}

        try:
            resp = self._get("cgi-bin/disk/disk_manage.cgi", params={"func": "get_all"})
            raw  = resp.text
        except Exception as e:
            print(f"[disk_smart][{self.ip_address}] error: {e}")
            return []

        auth = _x(raw, "authPassed")
        if auth != "1":
            print(f"[disk_smart][{self.ip_address}] authPassed={auth}")
            return []

        # 韌體 typo 為 "Ecnlosure"，同時支援正確拼字 "Enclosure"
        encl_tag = None
        for candidate in ["Ecnlosure_info", "Enclosure_info", "enclosure_info"]:
            if _re.search(rf'<{candidate}[\s>]', raw, _re.IGNORECASE):
                encl_tag = candidate
                break

        if not encl_tag:
            print(f"[disk_smart][{self.ip_address}] 找不到 Enclosure block tag，RAW前600:\n{raw[:600]}")
            return []

        print(f"[disk_smart][{self.ip_address}] 使用 enclosure tag: <{encl_tag}>")

        encl_blocks = _re.findall(
            rf'<{_re.escape(encl_tag)}[^>]*>(.*?)</{_re.escape(encl_tag)}>',
            raw, _re.DOTALL | _re.IGNORECASE
        )
        print(f"[disk_smart][{self.ip_address}] 找到 {len(encl_blocks)} 個 enclosure")

        result = []
        for block in encl_blocks:
            encl_id    = _x(block, "enclosureID")   or "0"
            encl_model  = _x(block, "enclModel")      or ""
            encl_slots = _x(block, "enclosureSlot") or "0"
            try:
                total_bays = int(encl_slots)
            except ValueError:
                total_bays = 0

            warnings = []
            errors   = []

            rows = _re.findall(r'<row>(.*?)</row>', block, _re.DOTALL | _re.IGNORECASE)
            for row in rows:
                hd_no    = _x(row, "hd_no")
                hd_smart = _x(row, "hd_smart")
                if not hd_no or hd_smart is None:
                    continue
                if hd_smart in ("1", "2"):
                    slot = int((hd_no.split(":")[-1] or "0"), 10)
                    entry = {
                        "hd_no":    hd_no,
                        "slot":     slot,
                        "hd_smart": hd_smart,
                        "label":    SMART_LABEL.get(hd_smart, f"異常({hd_smart})"),
                    }
                    if hd_smart == "1":
                        warnings.append(entry)
                    else:
                        errors.append(entry)

            result.append({
                "id":         encl_id,
                "model":      encl_model,
                "total_bays": total_bays,
                "warnings":   warnings,
                "errors":     errors,
            })
            print(f"[disk_smart][{self.ip_address}] Enclosure {encl_id} ({encl_model}): "
                  f"{total_bays} bays, {len(warnings)} warnings, {len(errors)} errors")

        return result

    def get_system_info(self) -> dict | None:
        """取得系統資訊 (sysinfo)，回傳 dict 或 None。"""
        if not self.sid:
            return None

        import time as _time
        import re as _re

        def _x(text, tag):
            m = _re.search(
                rf'<{_re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{_re.escape(tag)}>',
                text, _re.IGNORECASE | _re.DOTALL)
            return m.group(1).strip() if m else None

        def _xi(text, tag, default=0):
            v = _x(text, tag)
            try:
                return int(v) if v else default
            except Exception:
                return default

        params = {"subfunc": "sysinfo", "count": int(_time.time() * 1000)}
        try:
            resp = self._get("cgi-bin/management/manaRequest.cgi", params=params)
            raw  = resp.text
        except Exception as e:
            print(f"[sysinfo][{self.ip_address}] error: {e}")
            return None

        if _x(raw, "authPassed") != "1":
            print(f"[sysinfo][{self.ip_address}] authPassed 失敗")
            return None

        cpu_raw = (_x(raw, "cpu_usage") or "0").replace("%", "").strip()

        return {
            "server_name":   _x(raw,  "server_name"),
            "serial_number": _x(raw,  "serial_number"),
            "uptime_day":    _xi(raw, "uptime_day"),
            "uptime_hour":   _xi(raw, "uptime_hour"),
            "uptime_min":    _xi(raw, "uptime_min"),
            "uptime_sec":    _xi(raw, "uptime_sec"),
            "cpu_usage":     cpu_raw,
            "cpu_tempc":     _x(raw,  "cpu_tempc"),
            "sys_tempc":     _x(raw,  "sys_tempc"),
            "disk_num":      _xi(raw, "disk_num"),
            "ssd_num":       _xi(raw, "ssd_disk_num"),
            "m2_num":        _xi(raw, "m2_disk_num"),
        }

    def get_memory_info(self) -> dict | None:
        """取得記憶體使用狀況 (sysmonitor)，回傳 dict 或 None。"""
        if not self.sid:
            return None

        import re as _re

        def _x(text, tag):
            m = _re.search(
                rf'<{_re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{_re.escape(tag)}>',
                text, _re.IGNORECASE | _re.DOTALL)
            return m.group(1).strip() if m else None

        def _xi(text, tag, default=0):
            v = _x(text, tag)
            try:
                return int(v) if v else default
            except Exception:
                return default

        try:
            resp = self._get("cgi-bin/management/manaRequest.cgi",
                             params={"subfunc": "sysmonitor", "sys_memory_use": "1"})
            raw  = resp.text
        except Exception as e:
            print(f"[memory][{self.ip_address}] error: {e}")
            return None

        if _x(raw, "authPassed") != "1":
            return None

        total = _xi(raw, "mem_total")
        used  = _xi(raw, "mem_used")
        free  = _xi(raw, "mem_free")

        if total <= 0:
            return None

        if used == 0 and free > 0:
            used = total - free

        return {
            "total": total,
            "used":  used,
            "free":  free,
            "pct":   round(used / total * 100, 1) if total else 0,
        }

    def get_pool_info(self) -> list:
        """取得硬碟儲存池使用空間，回傳 list of dict（每個 pool 一筆）。"""
        if not self.sid:
            return []

        import re as _re

        def _x(text, tag):
            m = _re.search(
                rf'<{_re.escape(tag)}[^>]*>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</{_re.escape(tag)}>',
                text, _re.IGNORECASE | _re.DOTALL)
            return m.group(1).strip() if m else None

        def _parse_tb(s: str) -> float:
            """將 '261.74 TB' / '500.0 GB' 等字串統一轉為 TB (float)。"""
            if not s:
                return 0.0
            m = _re.match(r'([\d.]+)\s*(TB|GB|MB)', s.strip(), _re.IGNORECASE)
            if not m:
                return 0.0
            val, unit = float(m.group(1)), m.group(2).upper()
            return val if unit == 'TB' else val / 1024 if unit == 'GB' else val / 1024 / 1024

        pools = []
        for pool_id in range(1, 16):
            try:
                resp = self._get("cgi-bin/disk/disk_manage.cgi", params={
                    "func":       "extra_get",
                    "store":      "poolInfo",
                    "poolID":     pool_id,
                    "Pool_Info":  "1",
                })
                raw = resp.text
            except Exception as e:
                print(f"[pool][{self.ip_address}] pool_id={pool_id} error: {e}")
                break

            capacity  = _x(raw, "pool_capacity")
            allocated = _x(raw, "pool_allocated")
            freesize  = _x(raw, "pool_freesize")

            if not capacity:
                break

            cap_tb  = _parse_tb(capacity)
            free_tb = _parse_tb(freesize)
            used_tb = cap_tb - free_tb
            pct     = round(used_tb / cap_tb * 100, 1) if cap_tb > 0 else 0.0

            pools.append({
                "pool_id":   pool_id,
                "capacity":  capacity,
                "allocated": allocated or "-",
                "freesize":  freesize  or "-",
                "percent":   pct,
            })

        return pools

    def start_recording(self, camera_guid: str) -> bool:
        """啟動錄影方式"""
        if not self.sid:
            print("No SID available.")
            return False
            
        params = {
            "ver": "1.1.0"
        }
        endpoint = f"{self.get_qvr_prefix()}/camera/mrec/{camera_guid}/start"
        
        try:
            response = self._put(endpoint, params=params)
            data = response.json()
            return data.get("success", False)
        except requests.exceptions.RequestException as e:
            print(f"Error starting recording for {camera_guid}: {e}")
            return False
        except ValueError:
            print("Failed to parse JSON response.")
            return False

    def stop_recording(self, camera_guid: str) -> bool:
        """停止錄影方式"""
        if not self.sid:
            print("No SID available.")
            return False
            
        params = {
            "ver": "1.1.0"
        }
        endpoint = f"{self.get_qvr_prefix()}/camera/mrec/{camera_guid}/stop"
        
        try:
            response = self._put(endpoint, params=params)
            data = response.json()
            return data.get("success", False)
        except requests.exceptions.RequestException as e:
            print(f"Error stopping recording for {camera_guid}: {e}")
            return False
        except ValueError:
            print("Failed to parse JSON response.")
            return False

    def send_meta_data(self, vault_id: str, metadata_string: str) -> bool:
        """傳送 meta data 方式"""
        if not self.sid:
            print("No SID available.")
            return False
            
        endpoint = f"{self.get_qvr_prefix()}/qvrip/Event/recvNotify/GENERIC/{vault_id}"
        
        try:
            # 根據文件，Body 為自定義資料字串，我們將字串編碼後傳送
            response = self._post(endpoint, data=metadata_string.encode('utf-8'))
            data = response.json()
            return_status = data.get("ReturnStatus", {})
            return return_status.get("statusCode") == 0
        except requests.exceptions.RequestException as e:
            print(f"Error sending meta data to {vault_id}: {e}")
            return False
        except ValueError:
            print("Failed to parse JSON response.")
            return False

    def export_recording(self, camera_guid: str, stream: int, start_time: int, end_time: int) -> bool:
        """匯出影片作業方式"""
        if not self.sid:
            print("No SID available.")
            return False
            
        endpoint = f"{self.get_qvr_prefix()}/camera/recordingfile/{camera_guid}/{stream}"
        params = {
            "ver": "1.1.0",
            "start_time": start_time, # 需為 Timestamp (毫秒)
            "end_time": end_time      # 需為 Timestamp (毫秒)
        }
        
        try:
            # 根據文件，使用 PUT 方式
            response = self._put(endpoint, params=params)
            # 文件說明：「將會提供 MP4 檔案到您指定的 NAS 存儲路徑」
            # 只要沒有產生 HTTP Exception 且 status_code 為 200，即視為觸發成功
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Error exporting recording for {camera_guid}: {e}")
            return False

    def check_camera_status(self, camera_guid: str) -> dict:
        """檢查攝影機狀態 (回傳包含 status 與 rec_state 的 dict)"""
        if not self.sid:
            print("No SID available.")
            return {}
            
        params = {
            "ver": "1.1.0"
        }
        try:
            # 根據文件，使用與取得清單相同的 API
            response = self._get(f"{self.get_qvr_prefix()}/camera/list", params=params)
            json_resp = response.json()
            
            # 走訪 datas 陣列尋找符合的 guid
            cameras = json_resp.get("datas", [])
            for cam in cameras:
                if cam.get("guid") == camera_guid:
                    return {
                        "status": cam.get("status"),
                        "rec_state": cam.get("rec_state")
                    }
            print(f"Camera with GUID {camera_guid} not found.")
            return {}
        except requests.exceptions.RequestException as e:
            print(f"Error checking camera status for {camera_guid}: {e}")
            return {}
        except ValueError:
            print("Failed to parse JSON response.")
            return {}

    def get_all_http_share_link_status(self) -> dict:
        """取得 全部 http share link 啟用狀態 (回傳包含所有攝影機狀態的 dict)"""
        if not self.sid:
            print("No SID available.")
            return {}
            
        params = {"act": "get_all_status"}
        try:
            response = self._get(f"{self.get_qvr_prefix()}/apis/camera_status.cgi", params=params)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting all status: {e}")
            return {}
        except ValueError:
            print("Failed to parse JSON response.")
            return {}

    def check_http_share_link_by_guid(self, camera_guid: str) -> dict:
        """用 guid 查有無啟用 HTTP share link, 這隻也會回 stream 的資訊"""
        if not self.sid:
            print("No SID available.")
            return {}
            
        params = {
            "act": "show_share_status",
            "guid": camera_guid
        }
        try:
            response = self._get(f"{self.get_qvr_prefix()}/apis/sharelink_settings.cgi", params=params)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error checking share link for {camera_guid}: {e}")
            return {}
        except ValueError:
            print("Failed to parse JSON response.")
            return {}

    def enable_share_link(self, camera_guid: str, stream_id: int = 1, enable_vcode: bool = False, vcode: str = "", refresh: int = 0) -> dict:
        """啟用 share link"""
        if not self.sid:
            print("No SID available.")
            return {}
            
        params = {"act": "enable"}
        json_data = {
            "guid": camera_guid,
            "stream_id": stream_id,
            "enable_vcode": enable_vcode,
            "vcode": vcode,
            "refresh": refresh
        }
        
        try:
            response = self._post(f"{self.get_qvr_prefix()}/apis/sharelink_settings.cgi", params=params, json_data=json_data)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error enabling share link for {camera_guid}: {e}")
            return {}
        except ValueError:
            print("Failed to parse JSON response.")
            return {}

class QFaceApi(QVRApi):
    """QVR Face Insight 系統 API，繼承 QVRApi 認證機制，新增 get_about()。"""

    def get_about(self) -> dict:
        """呼叫 qvrfaceinsight/apis/about 取得系統版本與功能資訊。"""
        try:
            resp = self._get("qvrfaceinsight/apis/about")
            data = resp.json()
            return {
                "error_code":    data.get("error_code", -1),
                "error_message": data.get("error_message", ""),
                "functions":     data.get("functions", []),
                "server_name":   data.get("server_name", ""),
                "version":       data.get("version", ""),
            }
        except Exception as e:
            print(f"[qface_about][{self.ip_address}] error: {e}")
            return {
                "error_code":    -1,
                "error_message": str(e),
                "functions":     [],
                "server_name":   "",
                "version":       "",
            }

    def get_codec_license(self) -> str:
        """呼叫 qvrfaceinsight/apis/codec_license 取得授權類型，回傳如 'BASIC'。"""
        try:
            resp = self._get("qvrfaceinsight/apis/codec_license")
            data = resp.json()
            return data.get("codec_license", "")
        except Exception as e:
            print(f"[qface_license][{self.ip_address}] error: {e}")
            return ""

    def get_stream_tasks(self) -> dict:
        """呼叫 qvrfaceinsight/apis/stream_tasks 取得攝影機任務清單。"""
        try:
            resp = self._get("qvrfaceinsight/apis/stream_tasks")
            data = resp.json()
            tasks = []
            for t in data.get("tasks", []):
                events = t.get("events", [])
                tasks.append({
                    "camera_name":  t.get("camera_name", ""),
                    "ip_address":   t.get("ip_address", ""),
                    "media_status": t.get("media_status", ""),
                    "events":       [e.get("name", str(e)) if isinstance(e, dict) else str(e) for e in events],
                    "total_events": len(events),
                })
            return {
                "total_tasks": data.get("total_tasks", len(tasks)),
                "tasks":       tasks,
            }
        except Exception as e:
            print(f"[qface_stream_tasks][{self.ip_address}] error: {e}")
            return {"total_tasks": 0, "tasks": []}


def _build_api(config: dict, name: str):
    """依 SOFTWARE_TYPE 建立對應的 API 實例。"""
    software_type = config.get('SOFTWARE_TYPE', 'qvr').lower()
    cls = QFaceApi if software_type == 'qface' else QVRApi
    api = cls(
        config['IP_ADDRESS'],
        int(config.get('PORT', 8080)),
        config.get('USERNAME', ''),
        config.get('PASSWORD', '')
    )
    api.server_name = name
    return api


def load_servers_from_file(filepath: str) -> Dict[str, QVRApi]:
    """從設定檔中讀取並建立 QVRApi / QFaceApi 實例的字典"""
    import os
    servers = {}
    current_server_name = None
    current_config = {}

    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return servers

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            if current_server_name and 'IP_ADDRESS' in current_config:
                servers[current_server_name] = _build_api(current_config, current_server_name)
            current_server_name = None
            current_config = {}
            continue

        if ':' in line:
            parts = line.split(':', 1)
            key = parts[0].strip()
            value = parts[1].strip()

            if key.startswith('QVRServer_'):
                current_server_name = value
            else:
                current_config[key] = value

    # 處理最後一筆伺服器資料
    if current_server_name and 'IP_ADDRESS' in current_config:
        servers[current_server_name] = _build_api(current_config, current_server_name)

    return servers


def encode_password(plain: str) -> str:
    """將明碼密碼轉為 Base64"""
    return base64.b64encode(plain.encode('utf-8')).decode('utf-8')


def decode_password(password_base64: str) -> str:
    """將 Base64 密碼轉回明碼"""
    try:
        return base64.b64decode(password_base64).decode('utf-8')
    except Exception:
        return ""


def load_all_server_configs(filepath: str) -> list:
    """讀取所有伺服器設定（含原始 Base64 密碼），回傳 list of dict"""
    import os
    configs = []
    current_name = None
    current = {}

    if not os.path.exists(filepath):
        return configs

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    def _flush():
        if current_name and 'IP_ADDRESS' in current:
            configs.append({
                'name': current_name,
                'ip_address': current.get('IP_ADDRESS', ''),
                'port': int(current.get('PORT', 8080)),
                'username': current.get('USERNAME', ''),
                'password_base64': current.get('PASSWORD', ''),
                'software_type': current.get('SOFTWARE_TYPE', 'qvr').lower(),
            })

    for line in lines:
        line = line.strip()
        if not line:
            _flush()
            current_name = None
            current = {}
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            key, value = key.strip(), value.strip()
            if key.startswith('QVRServer_'):
                current_name = value
            else:
                current[key] = value

    _flush()
    return configs


def save_servers_to_file(filepath: str, configs: list):
    """將伺服器設定清單依序寫回設定檔，QVRServer_ 編號自動重排"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for i, cfg in enumerate(configs, 1):
            f.write(f"QVRServer_{i} : {cfg['name']}\n")
            f.write(f"IP_ADDRESS : {cfg['ip_address']}\n")
            f.write(f"PORT : {cfg['port']}\n")
            f.write(f"USERNAME : {cfg['username']}\n")
            f.write(f"PASSWORD : {cfg['password_base64']}\n")
            f.write(f"SOFTWARE_TYPE : {cfg.get('software_type', 'qvr')}\n")
            f.write("\n")


if __name__ == "__main__":
    servers = load_servers_from_file("serverlist.txt")
    for name, api in servers.items():
        print(f"Testing server: {name} ({api.ip_address})")
        # 優先嘗試 renew SID，若無 SID 或已過期則重新登入
        if api.sid and api.renew_sid():
            print(f"  -> SID renewed successfully! SID: {api.sid}")
        else:
            sid = api.get_sid()
            if sid:
                print(f"  -> Logged in (new SID)! SID: {sid}")
            else:
                print("  -> Login failed.")
