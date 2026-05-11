document.addEventListener('DOMContentLoaded', () => {
    fetchDashboardData();
    // Refresh every 30 seconds
    setInterval(fetchDashboardData, 30000);
});

async function fetchDashboardData() {
    try {
        const response = await fetch('/api/dashboard_data');
        const data = await response.json();
        
        document.getElementById('last-updated').textContent = `Last Updated: ${data.timestamp}`;
        
        renderServers(data.servers);
        renderCameraStats(data.servers);
        renderCameras(data.servers);
        renderAlarms(data.alarms);
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

function getStatusClass(status) {
    if (status.toUpperCase() === 'ONLINE') return 'status-online';
    if (status.toUpperCase() === 'OFFLINE') return 'status-offline';
    return 'status-warning';
}

function getCameraConnectionLabel(status) {
    const s = status.toUpperCase();
    if (s === 'NVR_CAM_CONNECTED' || s === 'NVR_CAM_CONNECTING') return { label: 'On Line', cls: 'status-online' };
    if (s === 'NVR_CAM_CONNECT_IDLE') return { label: 'IDLE', cls: 'status-idle' };
    if (s === 'NVR_CAM_DISCONNECTED') return { label: 'Off Line', cls: 'status-offline' };
    return { label: status, cls: 'status-warning' };
}

function renderCameraStats(servers) {
    let total = 0, online = 0, offline = 0, idle = 0, recording = 0, notRecording = 0;
    servers.forEach(server => {
        (server.cameras || []).forEach(cam => {
            total++;
            const conn = getCameraConnectionLabel(cam.status);
            if (conn.label === 'On Line') online++;
            else if (conn.label === 'IDLE') idle++;
            else offline++;
            const rec = getRecordingLabel(cam.rec_state);
            if (rec.label === 'Recording') recording++;
            else notRecording++;
        });
    });
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-online').textContent = online;
    document.getElementById('stat-offline').textContent = offline;
    document.getElementById('stat-idle').textContent = idle;
    document.getElementById('stat-recording').textContent = recording;
    document.getElementById('stat-not-recording').textContent = notRecording;
}

function getRecordingLabel(recState) {
    const s = recState.toUpperCase();
    if (s === 'RECORDING') return { label: 'Recording', cls: 'status-online' };
    if (s === 'NOT_RECORDING') return { label: 'Not Recording', cls: 'status-offline' };
    return { label: recState, cls: 'status-warning' };
}

function renderServers(servers) {
    const container = document.getElementById('servers-container');
    container.innerHTML = '';
    
    servers.forEach(server => {
        const card = document.createElement('div');
        card.className = 'server-card';
        
        card.innerHTML = `
            <div class="server-header">
                <div class="server-name">${server.name}</div>
                <div class="status-badge ${getStatusClass(server.status)}">${server.status}</div>
            </div>
            <div class="server-ip">IP : ${server.ip_address}</div>
            <div style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary);">
                Cameras : ${server.cameras ? server.cameras.length : 0}
            </div>
            <div class="server-card-actions">
                <button class="btn-edit" onclick="openServerModal('${server.name}')">Edit</button>
                <button class="btn-delete" onclick="deleteServer('${server.name}')">Delete</button>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderCameras(servers) {
    const container = document.getElementById('cameras-container');
    container.innerHTML = '';
    
    let hasCameras = false;
    servers.forEach(server => {
        if (!server.cameras || server.cameras.length === 0) return;
        hasCameras = true;
        
        const group = document.createElement('div');
        group.className = 'server-camera-group';
        
        let camerasHtml = '';
        server.cameras.forEach(cam => {
            const conn = getCameraConnectionLabel(cam.status);
            const rec = getRecordingLabel(cam.rec_state);
            camerasHtml += `
                <div class="camera-card">
                    <div class="camera-name">
                        <span>${cam.name}</span>
                        <span class="camera-id">#${cam.channel_index}</span>
                    </div>
                    <div class="camera-stats">
                        <div class="stat-row">
                            <span class="stat-label">Connection:</span>
                            <span class="status-badge ${conn.cls}">${conn.label}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Recording:</span>
                            <span class="status-badge ${rec.cls}">${rec.label}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        group.innerHTML = `
            <h3>${server.name} Cameras</h3>
            <div class="camera-grid">
                ${camerasHtml}
            </div>
        `;
        
        container.appendChild(group);
    });
    
    if (!hasCameras) {
        container.innerHTML = '<div style="color: var(--text-secondary);">No cameras found or failed to connect to servers.</div>';
    }
}

async function controlCamera(serverName, cameraGuid, action) {
    if (!confirm(`Are you sure you want to ${action === 'start_rec' ? 'START' : 'STOP'} recording for this camera?`)) return;
    
    try {
        const response = await fetch('/api/camera_action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server_name: serverName, camera_guid: cameraGuid, action: action })
        });
        const data = await response.json();
        
        if (data.success) {
            alert('Action completed successfully!');
            fetchDashboardData(); // Refresh data immediately
        } else {
            alert('Action failed: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error executing camera action:', error);
        alert('An error occurred while sending the command.');
    }
}

const ALARM_MAX = 50;
const ALARM_PAGE_SIZE = 10;
let alarmBuffer = [];
let alarmCurrentPage = 1;

function renderAlarms(newAlarms) {
    // 新資料插入最前面，保留最多 50 筆
    alarmBuffer = [...newAlarms, ...alarmBuffer].slice(0, ALARM_MAX);
    renderAlarmPage(alarmCurrentPage);
}

function renderAlarmPage(page) {
    const tbody = document.getElementById('alarms-body');
    const pagination = document.getElementById('alarms-pagination');
    tbody.innerHTML = '';

    if (alarmBuffer.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--success-color);">All systems nominal. No IDLE alarms.</td></tr>`;
        pagination.innerHTML = '';
        return;
    }

    const totalPages = Math.ceil(alarmBuffer.length / ALARM_PAGE_SIZE);
    page = Math.min(Math.max(page, 1), totalPages);
    alarmCurrentPage = page;

    const start = (page - 1) * ALARM_PAGE_SIZE;
    const pageItems = alarmBuffer.slice(start, start + ALARM_PAGE_SIZE);

    pageItems.forEach(alarm => {
        const tr = document.createElement('tr');
        const conn = getCameraConnectionLabel(alarm.camera_status);
        tr.innerHTML = `
            <td>${alarm.server_name}</td>
            <td>${alarm.camera_index}</td>
            <td>${alarm.camera_name}</td>
            <td><span class="status-badge ${conn.cls}">${conn.label}</span></td>
            <td>${alarm.timestamp}</td>
        `;
        tbody.appendChild(tr);
    });

    // 分頁按鈕
    pagination.innerHTML = '';
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.textContent = i;
        btn.className = 'page-btn' + (i === page ? ' page-btn-active' : '');
        btn.onclick = () => renderAlarmPage(i);
        pagination.appendChild(btn);
    }
}

// ── Password Visibility Toggle ───────────────────────────────────────────────

function togglePasswordVisibility() {
    const input  = document.getElementById('field-password');
    const eyeOpen   = document.getElementById('eye-open');
    const eyeClosed = document.getElementById('eye-closed');
    const isHidden  = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    eyeOpen.style.display   = isHidden ? 'none'  : '';
    eyeClosed.style.display = isHidden ? ''      : 'none';
}

// ── Server Management Modal ──────────────────────────────────────────────────

let _editingServerName = null;  // null = add mode, string = edit mode

async function openServerModal(serverName = null) {
    _editingServerName = serverName;
    const title = document.getElementById('modal-title');

    if (serverName) {
        title.textContent = 'Edit QVR Server';
        const configs = await fetch('/api/server_configs').then(r => r.json());
        const cfg = configs.find(c => c.name === serverName);
        if (cfg) {
            document.getElementById('field-name').value = cfg.name;
            document.getElementById('field-ip').value = cfg.ip_address;
            document.getElementById('field-port').value = cfg.port;
            document.getElementById('field-username').value = cfg.username;
            document.getElementById('field-password').value = cfg.password;
        }
    } else {
        title.textContent = 'Add QVR Server';
        document.getElementById('field-name').value = '';
        document.getElementById('field-ip').value = '';
        document.getElementById('field-port').value = '8080';
        document.getElementById('field-username').value = '';
        document.getElementById('field-password').value = '';
    }

    document.getElementById('server-modal-overlay').style.display = 'flex';
}

function closeServerModal() {
    document.getElementById('server-modal-overlay').style.display = 'none';
    _editingServerName = null;
}

async function saveServerConfig() {
    const payload = {
        name:       document.getElementById('field-name').value.trim(),
        ip_address: document.getElementById('field-ip').value.trim(),
        port:       parseInt(document.getElementById('field-port').value) || 8080,
        username:   document.getElementById('field-username').value.trim(),
        password:   document.getElementById('field-password').value,
    };

    if (!payload.name || !payload.ip_address || !payload.username || !payload.password) {
        alert('請填寫所有欄位');
        return;
    }

    const isEdit = _editingServerName !== null;
    const url = isEdit
        ? `/api/server_configs/${encodeURIComponent(_editingServerName)}`
        : '/api/server_configs';
    const method = isEdit ? 'PUT' : 'POST';

    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
        closeServerModal();
        fetchDashboardData();
    } else {
        alert('Error: ' + (data.message || 'Unknown error'));
    }
}

async function deleteServer(serverName) {
    if (!confirm(`確定要刪除伺服器「${serverName}」？`)) return;

    const res = await fetch(`/api/server_configs/${encodeURIComponent(serverName)}`, {
        method: 'DELETE',
    });
    const data = await res.json();

    if (data.success) {
        fetchDashboardData();
    } else {
        alert('Error: ' + (data.message || 'Unknown error'));
    }
}

// 點擊遮罩關閉 Modal
document.getElementById('server-modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('server-modal-overlay')) closeServerModal();
});
