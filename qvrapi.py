import base64
import requests
import re
import urllib.parse
from typing import Optional, Dict, Any, List

class QVRApi:
    def __init__(self, ip_address: str, port: int, username: str, password_base64: str):
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password_base64
        self.base_url = f"http://{self.ip_address}:{self.port}"
        self.sid = None

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
        """取得 SID 方式"""
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
                return self.sid
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting SID: {e}")
            return None

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

    def get_guid(self) -> list:
        """取得 GUID 方式 (取得攝影機列表與 GUID)"""
        if not self.sid:
            print("No SID available.")
            return []
            
        params = {
            "ver": "1.1.0"
        }
        try:
            response = self._get("qvrpro/camera/list", params=params)
            # 因為返回值是 JSON 格式，我們直接解析它
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error getting camera list: {e}")
            return []
        except ValueError:
            print("Failed to parse JSON response.")
            return []

    def start_recording(self, camera_guid: str) -> bool:
        """啟動錄影方式"""
        if not self.sid:
            print("No SID available.")
            return False
            
        params = {
            "ver": "1.1.0"
        }
        endpoint = f"qvrpro/camera/mrec/{camera_guid}/start"
        
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
        endpoint = f"qvrpro/camera/mrec/{camera_guid}/stop"
        
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
            
        endpoint = f"qvrpro/qvrip/Event/recvNotify/GENERIC/{vault_id}"
        
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
            
        endpoint = f"qvrpro/camera/recordingfile/{camera_guid}/{stream}"
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
            response = self._get("qvrpro/camera/list", params=params)
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
            response = self._get("qvrpro/apis/camera_status.cgi", params=params)
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
            response = self._get("qvrpro/apis/sharelink_settings.cgi", params=params)
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
            response = self._post("qvrpro/apis/sharelink_settings.cgi", params=params, json_data=json_data)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error enabling share link for {camera_guid}: {e}")
            return {}
        except ValueError:
            print("Failed to parse JSON response.")
            return {}

def load_servers_from_file(filepath: str) -> Dict[str, QVRApi]:
    """從設定檔中讀取並建立 QVRApi 實例的字典"""
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
                api = QVRApi(
                    current_config['IP_ADDRESS'],
                    int(current_config.get('PORT', 8080)),
                    current_config.get('USERNAME', ''),
                    current_config.get('PASSWORD', '')
                )
                api.server_name = current_server_name
                servers[current_server_name] = api
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
        api = QVRApi(
            current_config['IP_ADDRESS'],
            int(current_config.get('PORT', 8080)),
            current_config.get('USERNAME', ''),
            current_config.get('PASSWORD', '')
        )
        api.server_name = current_server_name
        servers[current_server_name] = api

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
