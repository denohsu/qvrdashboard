import sys
sys.path.append('d:/Python/QVRDashboard')
from main import get_dashboard_data
data = get_dashboard_data()
print(f"Alarms: {len(data['alarms'])}")
print(f"Server Alarms: {len(data['server_alarms'])}")
