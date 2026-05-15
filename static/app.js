let cameraGridState = JSON.parse(localStorage.getItem('cameraGridState')) || {}; // { 'ServerName': true (expanded) / false (collapsed) }

let _refreshTimer = null;

function _startRefreshTimer(seconds) {
    if (_refreshTimer) clearInterval(_refreshTimer);
    _refreshTimer = setInterval(fetchDashboardData, seconds * 1000);
}

window.onRefreshIntervalChange = function (value) {
    const seconds = parseInt(value);
    localStorage.setItem('refreshInterval', seconds);
    _startRefreshTimer(seconds);
};

document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('refreshInterval') || '30';
    const select = document.getElementById('refresh-interval-select');
    if (select) select.value = saved;
    fetchDashboardData();
    _startRefreshTimer(parseInt(saved));
});

async function fetchDashboardData() {
    try {
        const response = await fetch('/api/dashboard_data');
        const data = await response.json();

        document.getElementById('last-updated').textContent = `Last Updated: ${data.timestamp}`;

        renderServers(data.servers);
        renderCameraStats(data.servers);
        renderCameras(data.servers);
        renderServerAlarms(data.server_alarms || []);
        renderAlarms(data.alarms);
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

function getStatusClass(status) {
    const s = status.toUpperCase();
    if (s === 'ONLINE') return 'status-online';
    if (s === 'OFFLINE') return 'status-offline';
    if (s === 'SERVICE ERROR') return 'status-warning';
    return 'status-warning';
}

function getCameraConnectionLabel(status) {
    const s = status.toUpperCase();
    if (s === 'NVR_CAM_CONNECTED') return { label: 'On Line', cls: 'status-online' };
    if (s === 'NVR_CAM_CONNECT_IDLE') return { label: 'IDLE', cls: 'status-idle' };
    if (s === 'NVR_CAM_DISCONNECTED' || s === 'NVR_CAM_CONNECTING') return { label: 'Off Line', cls: 'status-offline' };
    return { label: status, cls: 'status-warning' };
}

function renderCameraStats(servers) {
    const qvrServers   = servers.filter(s => s.software_type !== 'qface');
    const qfaceServers = servers.filter(s => s.software_type === 'qface');

    // ── QVR ─────────────────────────────────────────────────────────────────
    let qvrOnline = 0, qvrOffline = 0;
    let total = 0, online = 0, offline = 0, idle = 0, recording = 0, notRecording = 0;

    qvrServers.forEach(server => {
        if (server.status.toUpperCase() === 'ONLINE') qvrOnline++;
        else qvrOffline++;

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

    const _set = (id, val) => { document.getElementById(id).textContent = val; };
    const _setRed = (id, val) => {
        const el = document.getElementById(id);
        el.textContent = val;
        el.style.textShadow = val > 0 ? '0 0 18px rgba(248,113,113,0.85), 0 0 6px rgba(248,113,113,0.5)' : 'none';
    };

    _set('stat-server-total', qvrServers.length);
    _set('stat-server-online', qvrOnline);
    _setRed('stat-server-offline', qvrOffline);
    _set('stat-total', total);
    _set('stat-online', online);
    _setRed('stat-offline', offline);
    _set('stat-idle', idle);
    _set('stat-recording', recording);
    _setRed('stat-not-recording', notRecording);

    // ── QFACE ────────────────────────────────────────────────────────────────
    let qfOnline = 0, qfOffline = 0;
    let taskTotal = 0, taskOnline = 0, taskOffline = 0;

    qfaceServers.forEach(server => {
        if (server.status.toUpperCase() === 'ONLINE') qfOnline++;
        else qfOffline++;

        const st = server.qface_stream_tasks || { total_tasks: 0, tasks: [] };
        taskTotal += st.total_tasks || 0;
        (st.tasks || []).forEach(t => {
            if ((t.media_status || '').toUpperCase() === 'MS_CONNECTED') taskOnline++;
            else taskOffline++;
        });
    });

    _set('stat-qface-server-total', qfaceServers.length);
    _set('stat-qface-server-online', qfOnline);
    _setRed('stat-qface-server-offline', qfOffline);
    _set('stat-qface-task-total', taskTotal);
    _set('stat-qface-task-online', taskOnline);
    _setRed('stat-qface-task-offline', taskOffline);
}

function getQFaceMediaStatus(status) {
    if ((status || '').toUpperCase() === 'MS_CONNECTED') {
        return { label: 'OnLine', cls: 'status-online' };
    }
    return { label: 'Offline', cls: 'status-offline' };
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

        // ── QFACE 伺服器卡片 ───────────────────────────────────────────────────
        if (server.software_type === 'qface') {
            const isOffline = server.status.toUpperCase() !== 'ONLINE';
            card.className = `server-card${isOffline ? ' blinking-border' : ''}`;
            const ab       = server.qface_about || {};
            const st       = server.qface_stream_tasks || { total_tasks: 0, tasks: [] };
            const version   = ab.version            || '-';
            const functions = (ab.functions || []).join(', ') || '-';
            const sysName   = ab.server_name         || server.name;
            const license   = ab.codec_license       || '-';
            const errHtml   = (!isOffline && ab.error_code !== 0 && ab.error_message)
                ? `<div style="margin-top:0.4rem;padding:0.4rem 0.6rem;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.35);border-radius:6px;font-size:0.75rem;color:var(--danger-color);">${ab.error_message}</div>`
                : '';

            const taskRows = (st.tasks || []).map(t => {
                const ms   = getQFaceMediaStatus(t.media_status);
                const evts = t.events.length > 0 ? t.events.join(' / ') : '-';
                return `<li style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:0.3rem;gap:0.4rem;">
                    <div style="display:flex;align-items:center;gap:0.3rem;overflow:hidden;flex:1;">
                        <span class="status-badge ${ms.cls}" style="font-size:0.6rem;padding:0.1rem 0.3rem;min-width:52px;text-align:center;">${ms.label}</span>
                        <span style="word-break:break-word;line-height:1.35;">${t.camera_name}</span>
                    </div>
                    <div style="font-size:0.72rem;color:var(--text-secondary);white-space:nowrap;text-align:right;">
                        <div>${t.ip_address || '-'}</div>
                        <div style="color:var(--accent-color);">Events: ${t.total_events} &nbsp;<span style="color:var(--text-secondary);font-size:0.68rem;">${evts}</span></div>
                    </div>
                </li>`;
            }).join('');

            card.innerHTML = `
                <div class="server-header">
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <span style="font-size:0.62rem;font-weight:700;padding:0.12rem 0.38rem;border-radius:4px;background:rgba(167,139,250,0.15);color:#a78bfa;border:1px solid rgba(167,139,250,0.35);text-transform:uppercase;letter-spacing:0.05em;">QFACE</span>
                        <div class="server-name">${server.name}</div>
                    </div>
                    <div class="status-badge ${getStatusClass(server.status)}">${server.status}</div>
                </div>
                <div class="server-ip">IP : ${server.ip_address}</div>
                <div style="margin-top:0.5rem;font-size:0.78rem;color:var(--text-secondary);">System Name : <span style="color:var(--text-primary);">${sysName}</span></div>
                <div style="font-size:0.78rem;color:var(--text-secondary);">Software : <span style="color:var(--accent-color);font-weight:500;">QFACE</span> <span style="color:var(--text-primary);">v${version}</span></div>
                <div style="font-size:0.78rem;color:var(--text-secondary);">License : <span style="color:var(--text-primary);">${license}</span></div>
                <div style="font-size:0.78rem;color:var(--text-secondary);">Functions : <span style="color:var(--text-primary);">${functions}</span></div>
                ${errHtml}
                <div style="margin-top:0.5rem;font-size:0.8rem;color:var(--text-secondary);display:flex;justify-content:space-between;align-items:center;">
                    <span>Tasks : ${st.total_tasks}</span>
                    <button class="btn-toggle-cams" onclick="toggleQFaceTasks(this)" style="background:none;border:none;color:var(--accent-color);cursor:pointer;">▼ Show</button>
                </div>
                <div class="server-cameras-list" style="display:none;margin-top:0.5rem;font-size:0.8rem;background:rgba(0,0,0,0.2);padding:0.5rem;border-radius:6px;">
                    <ul style="list-style:none;padding:0;margin:0;max-height:160px;overflow-y:auto;display:flex;flex-direction:column;gap:0.3rem;">
                        ${taskRows || '<li style="color:var(--text-secondary);text-align:center;padding:0.5rem 0;">No tasks</li>'}
                    </ul>
                </div>
                <div class="server-card-actions">
                    <button class="btn-sysinfo" onclick="openSysinfoModal('${server.name}')">系統狀態</button>
                    <button class="btn-edit" onclick="openServerModal('${server.name}')">Edit</button>
                    <button class="btn-delete" onclick="deleteServer('${server.name}')">Delete</button>
                </div>`;
            container.appendChild(card);
            return; // 跳過 QVR 渲染
        }

        // ── QVR 伺服器卡片 ────────────────────────────────────────────────────
        const isOffline = server.status.toUpperCase() !== 'ONLINE';
        const enclosures = server.disk_smart || [];
        const hasDiskAlert = enclosures.some(e => (e.warnings||[]).length > 0 || (e.errors||[]).length > 0);
        const blinkClass = isOffline ? 'blinking-border'
            : hasDiskAlert ? 'blinking-border-warning' : '';
        card.className = `server-card ${blinkClass}`;

        let camerasHtml = '';
        let recDaysStatsHtml = '';

        if (server.cameras && server.cameras.length > 0) {
            // Calculate rec days stats
            const stats = {};
            server.cameras.forEach(c => {
                const days = c.normal_rec_days || 0;
                stats[days] = (stats[days] || 0) + 1;
            });
            const sortedDays = Object.keys(stats).map(Number).sort((a, b) => b - a).slice(0, 4);
            const chips = sortedDays.map(days => {
                const count = stats[days];
                return `<span style="display:inline-flex;align-items:center;gap:0.15rem;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:5px;padding:0.12rem 0.45rem;font-size:0.72rem;white-space:nowrap;">
                    <span style="color:var(--text-secondary);">${days}d</span><span style="color:var(--text-primary);font-weight:700;margin-left:0.1rem;">×${count}</span>
                </span>`;
            }).join('');
            recDaysStatsHtml = `<div style="margin-top:0.65rem;">
                <div style="font-size:0.65rem;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.3rem;">錄影天數</div>
                <div style="display:flex;flex-wrap:wrap;gap:0.25rem;">${chips}</div>
            </div>`;

            // Build camera list HTML
            camerasHtml = server.cameras.map(c => {
                const connLabel = getCameraConnectionLabel(c.status);
                const recDays = c.normal_rec_days || 0;
                return `
                <li style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 0.3rem;">
                    <div style="display: flex; align-items: center; overflow: hidden;">
                        <span class="status-badge ${connLabel.cls}" style="font-size:0.6rem; padding:0.1rem 0.3rem; margin-right:0.3rem; min-width: 45px; text-align: center;">${connLabel.label}</span>
                        <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;" title="${c.name}">${c.name}</span>
                    </div>
                    <span style="font-size: 0.75rem; color: var(--text-secondary); background: rgba(255,255,255,0.05); padding: 0.15rem 0.4rem; border-radius: 4px; white-space: nowrap;">錄影天數: ${recDays} 天</span>
                </li>`;
            }).join('');
        } else {
            camerasHtml = '<li style="color: var(--text-secondary); text-align: center; padding: 0.5rem 0;">No cameras</li>';
        }

        // 儲存空間：優先用 pool_info（disk_manage API），fallback 用 disk_usage（chartReq API）
        let diskHtml = '';
        const pools = server.pool_info || [];
        const diskUsage = server.disk_usage || [];

        if (pools.length > 0) {
            diskHtml = '<div class="sysinfo-box" style="margin-top:0.6rem; padding:0.5rem 0.75rem; gap:0.3rem;">' +
                '<span class="sysinfo-box-label" style="font-size:0.7rem;">Storage Pool</span>' +
                pools.map(p => {
                    const pct = Math.min(p.percent, 100);
                    const barColor = pct >= 90 ? 'var(--danger-color)' : pct >= 75 ? 'var(--warning-color)' : 'var(--success-color)';
                    const barGlow = pct >= 90 ? `box-shadow:0 0 8px ${barColor};` : '';
                    return `<div style="margin-bottom:0.25rem;">
                        <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--text-secondary);margin-bottom:0.15rem;">
                            <span style="font-weight:500;color:var(--text-primary);">Pool ${p.pool_id}</span>
                            <span>${p.freesize} 可用 / ${p.capacity} (${p.percent}%)</span>
                        </div>
                        <div style="background:rgba(255,255,255,0.08);border-radius:6px;height:7px;overflow:hidden;">
                            <div style="width:${pct}%;height:100%;background:${barColor};border-radius:6px;transition:width 0.4s;${barGlow}"></div>
                        </div>
                    </div>`;
                }).join('') +
                '</div>';
        } else if (diskUsage.length > 0) {
            const fmtGB = gb => gb >= 1024 ? (gb / 1024).toFixed(1) + ' TB' : gb.toFixed(1) + ' GB';
            diskHtml = '<div class="sysinfo-box" style="margin-top:0.6rem; padding:0.5rem 0.75rem; gap:0.3rem;">' +
                '<span class="sysinfo-box-label" style="font-size:0.7rem;">Storage Usage</span>' +
                diskUsage.map(d => {
                    const pct = Math.min(d.percent, 100);
                    const barColor = pct >= 90 ? 'var(--danger-color)' : pct >= 75 ? 'var(--warning-color)' : 'var(--success-color)';
                    const barGlow = pct >= 90 ? `box-shadow:0 0 8px ${barColor};` : '';
                    return `<div style="margin-bottom:0.2rem;">
                        <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--text-secondary);margin-bottom:0.15rem;">
                            <span style="font-weight:500;color:var(--text-primary);">${d.name}</span>
                            <span>${fmtGB(d.used_gb)} / ${fmtGB(d.total_gb)} (${d.percent}%)</span>
                        </div>
                        <div style="background:rgba(255,255,255,0.08);border-radius:6px;height:7px;overflow:hidden;">
                            <div style="width:${pct}%;height:100%;background:${barColor};border-radius:6px;transition:width 0.4s;${barGlow}"></div>
                        </div>
                    </div>`;
                }).join('') +
                '</div>';
        }

        // 硬碟狀態 HTML：分兩個獨立區塊
        // 區塊 1（紅色）：有 disk 問題的 enclosure（Host 或 External）
        // 區塊 2（白色）：健康的 External enclosure（bays>0，無問題）
        const enclLabel = e => {
            const isHost = e.id === '0' || e.id === 0;
            const loc    = isHost ? 'Host' : `External ${e.id}`;
            const model  = e.model ? ' - ' + e.model : '';
            const bay    = !isHost ? ` &nbsp;·&nbsp; ${e.total_bays} Bay` : '';
            return `${loc}${model}${bay}`;
        };

        const alertEnclosures   = enclosures.filter(e => (e.warnings||[]).length > 0 || (e.errors||[]).length > 0);
        const healthyExternals  = enclosures.filter(e => {
            const isExternal = e.id !== '0' && e.id !== 0;
            const hasIssues  = (e.warnings||[]).length > 0 || (e.errors||[]).length > 0;
            return isExternal && !hasIssues && (e.total_bays || 0) > 0;
        });

        let smartHtml = '';

        // ── 異常區塊（紅色） ──────────────────────────────
        if (alertEnclosures.length > 0) {
            const alertRows = alertEnclosures.map(e => {
                const isHost = e.id === '0' || e.id === 0;
                const diskItems = [
                    ...(e.errors || []).map(d =>
                        `<div style="display:flex;align-items:center;gap:0.35rem;font-size:0.72rem;">
                            <span style="color:var(--danger-color);">✕</span>
                            <span style="color:var(--text-secondary);">硬碟 ${d.slot}</span>
                            <span style="color:var(--danger-color);font-weight:600;">${d.label}</span>
                        </div>`),
                    ...(e.warnings || []).map(d =>
                        `<div style="display:flex;align-items:center;gap:0.35rem;font-size:0.72rem;">
                            <span style="color:var(--warning-color);">⚠</span>
                            <span style="color:var(--text-secondary);">硬碟 ${d.slot}</span>
                            <span style="color:var(--warning-color);font-weight:600;">${d.label}</span>
                        </div>`),
                ].join('');
                return `<div style="margin-bottom:0.2rem;">
                    <div style="font-size:0.68rem;color:var(--danger-color);font-weight:600;">
                        ${enclLabel(e)}${isHost ? ` &nbsp;·&nbsp; ${e.total_bays} Bay` : ''}
                    </div>
                    ${diskItems}
                </div>`;
            }).join('');
            smartHtml += `<div style="margin-top:0.5rem;padding:0.5rem 0.75rem;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.35);border-radius:6px;display:flex;flex-direction:column;gap:0.15rem;">
                <span style="font-size:0.68rem;color:var(--danger-color);text-transform:uppercase;letter-spacing:0.05em;font-weight:600;">硬碟狀態警示</span>
                ${alertRows}
            </div>`;
        }

        // ── 擴充主機區塊（白色，無異常） ────────────────────
        if (healthyExternals.length > 0) {
            const extRows = healthyExternals.map(e =>
                `<div style="font-size:0.68rem;color:var(--text-primary);font-weight:600;">
                    擴充主機 ─ ${enclLabel(e)}
                </div>`
            ).join('');
            smartHtml += `<div style="margin-top:0.4rem;padding:0.5rem 0.75rem;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.12);border-radius:6px;display:flex;flex-direction:column;gap:0.15rem;">
                ${extRows}
            </div>`;
        }

        card.innerHTML = `
            <div class="server-header">
                <div style="display:flex;align-items:center;gap:0.4rem;">
                    <span style="font-size:0.62rem;font-weight:700;padding:0.12rem 0.38rem;border-radius:4px;background:rgba(59,130,246,0.15);color:var(--accent-color);border:1px solid rgba(59,130,246,0.3);text-transform:uppercase;letter-spacing:0.05em;">QVR</span>
                    <div class="server-name">${server.name}</div>
                </div>
                <div class="status-badge ${getStatusClass(server.status)}">${server.status}</div>
            </div>
            <div class="server-ip">IP : ${server.ip_address}</div>
            ${diskHtml}
            ${smartHtml}
            <div class="server-ip" style="margin-top: 0.6rem;">System : ${server.qvr_prefix || 'Unknown'}</div>
            ${recDaysStatsHtml}
            <div style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center;">
                <span>Cameras : ${server.cameras ? server.cameras.length : 0}</span>
                <button class="btn-toggle-cams" onclick="toggleCameras(this)" style="background:none; border:none; color:var(--accent-color); cursor:pointer;">▼ Show</button>
            </div>
            <div class="server-cameras-list" style="display:none; margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-primary); background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 6px;">
                <ul style="list-style: none; padding: 0; margin: 0; max-height: 120px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.3rem;">
                    ${camerasHtml}
                </ul>
            </div>
            <div class="server-card-actions">
                <button class="btn-sysinfo" onclick="openSysinfoModal('${server.name}')">系統狀態</button>
                <button class="btn-edit" onclick="openServerModal('${server.name}')">Edit</button>
                <button class="btn-delete" onclick="deleteServer('${server.name}')">Delete</button>
            </div>
        `;
        container.appendChild(card);
    });
}

window.toggleCameras = function (btn) {
    const list = btn.parentElement.nextElementSibling;
    if (list.style.display === 'none') {
        list.style.display = 'block';
        btn.textContent = '▲ Hide';
    } else {
        list.style.display = 'none';
        btn.textContent = '▼ Show';
    }
}

window.toggleQFaceTasks = function (btn) {
    const list = btn.parentElement.nextElementSibling;
    if (list.style.display === 'none') {
        list.style.display = 'block';
        btn.textContent = '▲ Hide';
    } else {
        list.style.display = 'none';
        btn.textContent = '▼ Show';
    }
}

function renderCameras(servers) {
    const container = document.getElementById('cameras-container');
    container.innerHTML = '';

    let hasCameras = false;
    servers.forEach(server => {
        if (!server.cameras || server.cameras.length === 0) return;
        hasCameras = true;

        const group = document.createElement('div');

        let camerasHtml = '';
        let hasAbnormalCamera = false;
        let offlineCamCount = 0;

        server.cameras.forEach(cam => {
            const conn = getCameraConnectionLabel(cam.status);
            const rec = getRecordingLabel(cam.rec_state);

            let cardBlinkClass = '';
            if (conn.label !== 'On Line' && conn.label !== 'IDLE') {
                hasAbnormalCamera = true;
                offlineCamCount++;
                cardBlinkClass = 'blinking-border';
            }

            camerasHtml += `
                <div class="camera-card ${cardBlinkClass}">
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
                        <div class="stat-row">
                            <span class="stat-label">錄影天數:</span>
                            <span class="status-badge" style="background: rgba(255,255,255,0.1); color: #fff;">${cam.normal_rec_days || 0} 天</span>
                        </div>
                        <div style="border-top: 1px solid rgba(255,255,255,0.05); margin: 0.4rem 0; padding-top: 0.4rem; display: flex; flex-direction: column; gap: 0.25rem;">
                            <div class="stat-row">
                                <span class="stat-label">品牌:</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${cam.brand || '-'}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">型號:</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${cam.model || '-'}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">格式:</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${cam.video_codec_setting || '-'}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">解析度:</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${cam.video_resolution_setting || '-'}</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">FPS:</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${cam.frame_rate_setting || '-'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        const isExpanded = cameraGridState[server.name] !== false; // default true
        const gridDisplay = isExpanded ? 'grid' : 'none';
        const iconTransform = isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)';
        const blinkClass = (!isExpanded && hasAbnormalCamera) ? 'blinking-border' : '';

        group.className = `server-camera-group ${blinkClass}`;
        group.dataset.hasAbnormal = hasAbnormalCamera ? 'true' : 'false';

        const offlineBadgeHtml = offlineCamCount > 0
            ? `<span style="display:inline-flex;align-items:center;gap:0.2rem;background:rgba(239,68,68,0.18);color:#f87171;border:1px solid rgba(239,68,68,0.4);border-radius:10px;padding:0.1rem 0.5rem;font-size:0.7rem;font-weight:600;margin-left:0.5rem;">⚠ ${offlineCamCount} Offline</span>`
            : '';

        group.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none;" onclick="toggleCameraGrid(this, '${server.name}')">
                <h3 style="margin: 0; color: var(--accent-color); display:flex; align-items:center;">${server.name} Cameras${offlineBadgeHtml}</h3>
                <span class="toggle-icon" style="color: var(--text-secondary); transition: transform 0.2s; transform: ${iconTransform};">▼</span>
            </div>
            <div class="camera-grid" style="margin-top: 1rem; display: ${gridDisplay};">
                ${camerasHtml}
            </div>
        `;

        container.appendChild(group);
    });

    if (!hasCameras) {
        container.innerHTML = '<div style="color: var(--text-secondary);">No cameras found or failed to connect to servers.</div>';
    }
}

window.toggleCameraGrid = function (header, serverName) {
    const group = header.parentElement;
    const grid = header.nextElementSibling;
    const icon = header.querySelector('.toggle-icon');

    if (grid.style.display === 'none') {
        grid.style.display = 'grid';
        icon.style.transform = 'rotate(0deg)';
        cameraGridState[serverName] = true;
        group.classList.remove('blinking-border');
    } else {
        grid.style.display = 'none';
        icon.style.transform = 'rotate(-90deg)';
        cameraGridState[serverName] = false;
        if (group.dataset.hasAbnormal === 'true') {
            group.classList.add('blinking-border');
        }
    }
    localStorage.setItem('cameraGridState', JSON.stringify(cameraGridState));
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

// ── Server Connection Alarms ─────────────────────────────────────────────────

const SERVER_ALARM_PAGE_SIZE = 10;
let serverAlarmBuffer = [];
let serverAlarmCurrentPage = 1;

function renderServerAlarms(newAlarms) {
    serverAlarmBuffer = [...newAlarms];
    renderServerAlarmPage(serverAlarmCurrentPage);
}

function renderServerAlarmPage(page) {
    const tbody = document.getElementById('server-alarms-body');
    const pagination = document.getElementById('server-alarms-pagination');
    tbody.innerHTML = '';

    if (serverAlarmBuffer.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--success-color);">All servers connected normally.</td></tr>`;
        pagination.innerHTML = '';
        return;
    }

    const totalPages = Math.ceil(serverAlarmBuffer.length / SERVER_ALARM_PAGE_SIZE);
    page = Math.min(Math.max(page, 1), totalPages);
    serverAlarmCurrentPage = page;

    const start = (page - 1) * SERVER_ALARM_PAGE_SIZE;
    serverAlarmBuffer.slice(start, start + SERVER_ALARM_PAGE_SIZE).forEach(alarm => {
        const isOffline = alarm.status === 'Offline';
        const statusCls = isOffline ? 'status-offline' : 'status-warning';
        const icon = isOffline ? '✕ ' : '⚠ ';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${alarm.server_name}</td>
            <td>${alarm.ip_address}</td>
            <td><span class="status-badge ${statusCls}">${icon}${alarm.status}</span></td>
            <td>${alarm.timestamp}</td>
        `;
        tbody.appendChild(tr);
    });

    pagination.innerHTML = '';
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.textContent = i;
        btn.className = 'page-btn' + (i === page ? ' page-btn-active' : '');
        btn.onclick = () => renderServerAlarmPage(i);
        pagination.appendChild(btn);
    }
}

const ALARM_PAGE_SIZE = 10;
let alarmBuffer = [];
let alarmCurrentPage = 1;

function renderAlarms(newAlarms) {
    // 僅顯示刷新當下的資料
    alarmBuffer = [...newAlarms];
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
        const icon = conn.cls === 'status-offline' ? '✕ ' : '⚠ ';
        tr.innerHTML = `
            <td>${alarm.server_name}</td>
            <td>${alarm.camera_index}</td>
            <td>${alarm.camera_name}</td>
            <td><span class="status-badge ${conn.cls}">${icon}${conn.label}</span></td>
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
    const input = document.getElementById('field-password');
    const eyeOpen = document.getElementById('eye-open');
    const eyeClosed = document.getElementById('eye-closed');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    eyeOpen.style.display = isHidden ? 'none' : '';
    eyeClosed.style.display = isHidden ? '' : 'none';
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
            document.getElementById('field-software-type').value = cfg.software_type || 'qvr';
            document.getElementById('field-name').value = cfg.name;
            document.getElementById('field-ip').value = cfg.ip_address;
            document.getElementById('field-port').value = cfg.port;
            document.getElementById('field-username').value = cfg.username;
            document.getElementById('field-password').value = cfg.password;
        }
    } else {
        title.textContent = 'Add QVR Server';
        document.getElementById('field-software-type').value = 'qvr';
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
        software_type: document.getElementById('field-software-type').value,
        name: document.getElementById('field-name').value.trim(),
        ip_address: document.getElementById('field-ip').value.trim(),
        port: parseInt(document.getElementById('field-port').value) || 8080,
        username: document.getElementById('field-username').value.trim(),
        password: document.getElementById('field-password').value,
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

// ── System Info Modal ────────────────────────────────────────────────────────

async function openSysinfoModal(serverName) {
    document.getElementById('sysinfo-modal-title').textContent = `系統狀態 ─ ${serverName}`;
    document.getElementById('sysinfo-content').innerHTML =
        '<div style="text-align:center;color:var(--text-secondary);padding:2rem;">讀取中...</div>';
    document.getElementById('sysinfo-modal-overlay').style.display = 'flex';

    try {
        const res = await fetch(`/api/system_info/${encodeURIComponent(serverName)}`);
        const data = await res.json();
        if (data.success) {
            renderSysinfoContent(data);
        } else {
            document.getElementById('sysinfo-content').innerHTML =
                `<div style="color:var(--danger-color);padding:1rem;">Error: ${data.message}</div>`;
        }
    } catch (e) {
        document.getElementById('sysinfo-content').innerHTML =
            `<div style="color:var(--danger-color);padding:1rem;">Failed to load.</div>`;
    }
}

function closeSysinfoModal() {
    document.getElementById('sysinfo-modal-overlay').style.display = 'none';
}

document.getElementById('sysinfo-modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('sysinfo-modal-overlay')) closeSysinfoModal();
});

function renderSysinfoContent(data) {
    const s = data.sysinfo || {};
    const m = data.memory || {};
    const disks = data.disk_usage || [];
    const pools = data.pool_info || [];
    const smartAlerts = data.disk_smart || [];

    const uptime = `${s.uptime_day || 0}d ${s.uptime_hour || 0}h ${s.uptime_min || 0}m ${s.uptime_sec || 0}s`;
    const fmtGB = gb => gb >= 1024 ? (gb / 1024).toFixed(1) + ' TB' : gb.toFixed(1) + ' GB';

    // 將 KB 值自動換算為最適合的單位
    const fmtKB = kb => {
        if (kb === null || kb === undefined) return 'N/A';
        const G = 1024, M = G * 1024, T = M * 1024, P = T * 1024;
        if (kb >= P) return (kb / P).toFixed(2) + ' PB';
        if (kb >= T) return (kb / T).toFixed(2) + ' TB';
        if (kb >= M) return (kb / M).toFixed(1) + ' GB';
        if (kb >= G) return (kb / G).toFixed(0) + ' MB';
        return kb.toFixed(0) + ' KB';
    };

    const box = (label, value) =>
        `<div class="sysinfo-box"><span class="sysinfo-box-label">${label}</span><span class="sysinfo-box-value">${value}</span></div>`;

    const fullRow = (content) =>
        `<div class="sysinfo-full">${content}</div>`;

    // ── QFACE 系統狀態 ──────────────────────────────────────────────────────
    if (data.software_type === 'qface') {
        const ab      = data.qface_about || {};
        const st      = data.qface_stream_tasks || { total_tasks: 0, tasks: [] };
        const isOk    = ab.error_code === 0;
        const funcs   = (ab.functions || []).join(', ') || '-';
        const license = ab.codec_license || '-';

        const statusBox = isOk
            ? `<div class="sysinfo-box" style="gap:0.3rem;">
                   <span class="sysinfo-box-label">Status</span>
                   <span class="status-badge status-online" style="width:fit-content;">正常</span>
               </div>`
            : `<div class="sysinfo-box blinking-border" style="background:rgba(239,68,68,0.06);gap:0.3rem;">
                   <span class="sysinfo-box-label" style="color:var(--danger-color);">Status</span>
                   <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">
                       <span class="status-badge status-offline">異常 (${ab.error_code})</span>
                       <span style="font-size:0.82rem;color:var(--danger-color);">${ab.error_message || ''}</span>
                   </div>
               </div>`;

        const taskTableRows = (st.tasks || []).map(t => {
            const ms   = getQFaceMediaStatus(t.media_status);
            const evts = t.events.length > 0 ? t.events.join(', ') : '-';
            return `<tr>
                <td style="font-size:0.82rem;">${t.camera_name || '-'}</td>
                <td style="font-size:0.82rem;color:var(--text-secondary);">${t.ip_address || '-'}</td>
                <td><span class="status-badge ${ms.cls}" style="font-size:0.72rem;">${ms.label}</span></td>
                <td style="font-size:0.78rem;color:var(--text-secondary);">
                    <span style="color:var(--accent-color);font-weight:600;">${t.total_events}</span>
                    &nbsp;<span style="font-size:0.72rem;">${evts}</span>
                </td>
            </tr>`;
        }).join('');

        const tasksSection = `
            <div class="sysinfo-full">
                <div class="sysinfo-box" style="gap:0.5rem;padding:0.75rem 1rem;">
                    <span class="sysinfo-box-label" style="margin-bottom:0.25rem;">Stream Tasks (${st.total_tasks})</span>
                    ${st.tasks.length > 0
                        ? `<div style="overflow-x:auto;">
                               <table style="width:100%;border-collapse:collapse;font-size:0.82rem;">
                                   <thead>
                                       <tr style="border-bottom:1px solid var(--glass-border);">
                                           <th style="text-align:left;padding:0.3rem 0.5rem;font-size:0.72rem;color:var(--text-secondary);font-weight:500;">Camera</th>
                                           <th style="text-align:left;padding:0.3rem 0.5rem;font-size:0.72rem;color:var(--text-secondary);font-weight:500;">IP</th>
                                           <th style="text-align:left;padding:0.3rem 0.5rem;font-size:0.72rem;color:var(--text-secondary);font-weight:500;">Status</th>
                                           <th style="text-align:left;padding:0.3rem 0.5rem;font-size:0.72rem;color:var(--text-secondary);font-weight:500;">Events</th>
                                       </tr>
                                   </thead>
                                   <tbody>${taskTableRows}</tbody>
                               </table>
                           </div>`
                        : `<div style="color:var(--text-secondary);font-size:0.85rem;padding:0.25rem 0;">No tasks available.</div>`}
                </div>
            </div>`;

        document.getElementById('sysinfo-content').innerHTML = `
            <div class="sysinfo-grid">
                ${box('Server Name', ab.server_name || '-')}
                ${box('Version', ab.version || '-')}
                ${box('License', license)}
                ${fullRow(statusBox)}
                ${fullRow(box('System', funcs))}
                ${tasksSection}
            </div>`;
        return;
    }

    let memHtml = 'N/A';
    if (m.total) {
        const pct = m.pct || 0;
        const barColor = pct >= 90 ? 'var(--danger-color)' : pct >= 70 ? 'var(--warning-color)' : 'var(--success-color)';
        memHtml = `
            <div style="display:flex;flex-direction:column;gap:0.35rem;width:100%; margin-top:0.25rem;">
                <span class="sysinfo-box-value">${fmtKB(m.used)} / ${fmtKB(m.total)} (${pct}%)</span>
                <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:6px;overflow:hidden;">
                    <div style="width:${pct}%;height:100%;background:${barColor};border-radius:4px;"></div>
                </div>
            </div>`;
    }

    const poolBarRow = p => {
        const pct = Math.min(p.percent, 100);
        const barColor = pct >= 90 ? 'var(--danger-color)' : pct >= 75 ? 'var(--warning-color)' : 'var(--success-color)';
        return `
        <div style="margin-bottom:0.75rem;">
            <div style="display:flex;justify-content:space-between;font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.3rem;">
                <span style="font-weight:500;color:var(--text-primary);">Pool ${p.pool_id}</span>
                <span>${p.freesize} 可用 / ${p.capacity} (${p.percent}%)</span>
            </div>
            <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:8px;overflow:hidden;">
                <div style="width:${pct}%;height:100%;background:${barColor};border-radius:4px;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-secondary);margin-top:0.2rem;">
                <span>已分配 ${p.allocated}</span>
                <span>總容量 ${p.capacity}</span>
            </div>
        </div>`;
    };

    let diskRows = '';
    if (disks.length > 0) {
        diskRows = `<div class="sysinfo-box" style="gap:0;"><span class="sysinfo-box-label" style="margin-bottom:0.5rem;">Disk Usage</span>` +
            disks.map(d => {
                const pct = Math.min(d.percent, 100);
                const barColor = pct >= 90 ? 'var(--danger-color)' : pct >= 75 ? 'var(--warning-color)' : 'var(--success-color)';
                return `<div class="sysinfo-row sysinfo-disk-row">
                <span class="sysinfo-label" style="font-weight:500;color:var(--text-primary);">${d.name}</span>
                <div style="flex:1;margin:0 0.75rem;">
                    <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:6px;overflow:hidden;">
                        <div style="width:${pct}%;height:100%;background:${barColor};border-radius:4px;"></div>
                    </div>
                </div>
                <span style="font-size:0.8rem;color:var(--text-secondary);white-space:nowrap;">
                    ${fmtGB(d.used_gb)} / ${fmtGB(d.total_gb)} (${d.percent}%)
                </span>
            </div>`;
            }).join('') + `</div>`;
    }

    let poolRows = '';
    if (pools.length > 0) {
        poolRows = `<div class="sysinfo-box"><span class="sysinfo-box-label" style="margin-bottom:0.5rem;">Storage Pool</span>` +
            pools.map(poolBarRow).join('') + `</div>`;
    }

    let smartRows = '';
    const modalEnclLabel = e => {
        const isHost = e.id === '0' || e.id === 0;
        const loc    = isHost ? 'Host' : `External ${e.id}`;
        const model  = e.model ? ' - ' + e.model : '';
        const bay    = !isHost ? ` · ${e.total_bays} Bay` : '';
        return `${loc}${model}${bay}`;
    };
    const modalAlerts   = smartAlerts.filter(e => (e.warnings||[]).length > 0 || (e.errors||[]).length > 0);
    const modalHealthy  = smartAlerts.filter(e => {
        const isExternal = e.id !== '0' && e.id !== 0;
        const hasIssues  = (e.warnings||[]).length > 0 || (e.errors||[]).length > 0;
        return isExternal && !hasIssues && (e.total_bays || 0) > 0;
    });

    // 異常區塊（紅色）
    if (modalAlerts.length > 0) {
        const alertBlocks = modalAlerts.map(e => {
            const isHost = e.id === '0' || e.id === 0;
            const diskItems = [
                ...(e.errors || []).map(d =>
                    `<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.82rem;">
                        <span style="color:var(--danger-color);">✕</span>
                        <span style="color:var(--text-secondary);">硬碟 ${d.slot}</span>
                        <span class="status-badge status-offline">${d.label}</span>
                    </div>`),
                ...(e.warnings || []).map(d =>
                    `<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.82rem;">
                        <span style="color:var(--warning-color);">⚠</span>
                        <span style="color:var(--text-secondary);">硬碟 ${d.slot}</span>
                        <span class="status-badge status-warning">${d.label}</span>
                    </div>`),
            ].join('');
            return `<div class="sysinfo-box blinking-border" style="background:rgba(239,68,68,0.06);gap:0.4rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="sysinfo-box-label" style="color:var(--danger-color);">硬碟異常 ─ ${modalEnclLabel(e)}</span>
                    ${isHost ? `<span style="font-size:0.75rem;color:var(--text-secondary);">${e.total_bays} Bay</span>` : ''}
                </div>
                ${diskItems}
            </div>`;
        }).join('');
        smartRows += fullRow(alertBlocks);
    }

    // 擴充主機區塊（白色，無異常）
    if (modalHealthy.length > 0) {
        const healthyBlocks = modalHealthy.map(e =>
            `<div class="sysinfo-box" style="border-color:rgba(255,255,255,0.12);background:rgba(255,255,255,0.02);gap:0.25rem;">
                <span class="sysinfo-box-label">擴充主機</span>
                <span class="sysinfo-box-value" style="font-size:0.85rem;">${modalEnclLabel(e)}</span>
            </div>`
        ).join('');
        smartRows += fullRow(healthyBlocks);
    }

    document.getElementById('sysinfo-content').innerHTML = `
        <div class="sysinfo-grid">
            ${box('Server Name', s.server_name || '-')}
            ${box('Serial', s.serial_number || '-')}
            ${fullRow(box('Uptime', uptime))}
            ${box('CPU Usage', (s.cpu_usage || '-') + ' %')}
            ${box('CPU Temp', (s.cpu_tempc || '-') + ' °C')}
            ${box('System Temp', (s.sys_tempc || '-') + ' °C')}
            ${box('Disks', `HDD: ${s.disk_num || 0} &nbsp;|&nbsp; SSD: ${s.ssd_num || 0} &nbsp;|&nbsp; M.2: ${s.m2_num || 0}`)}
            ${fullRow(`<div class="sysinfo-box"><span class="sysinfo-box-label">Memory</span>${memHtml}</div>`)}
            ${diskRows ? fullRow(diskRows) : ''}
            ${poolRows ? fullRow(poolRows) : ''}
            ${smartRows}
        </div>`;
}

// ── Logs Modal ───────────────────────────────────────────────────────────────

let _logsState    = { type: 'camera', offset: 0, loading: false, hasMore: true };
let _logsObserver = null;

async function openLogsModal(type = 'camera') {
    // 重設狀態
    _logsState = { type, offset: 0, loading: false, hasMore: true };

    document.getElementById('logs-modal-overlay').style.display = 'flex';
    const content = document.getElementById('logs-content');
    const title   = document.querySelector('#logs-modal-overlay .modal-header h3');
    title.textContent = (type === 'camera' ? 'Camera' : 'Server') + ' Alarm Log History (Up to 14 days)';

    // 清空並建立結構：<pre> 放文字、<div> sentinel 偵測捲動底部
    content.innerHTML =
        '<pre id="logs-text" style="margin:0;font-size:0.88rem;line-height:1.5;white-space:pre-wrap;word-break:break-all;"></pre>' +
        '<div id="logs-sentinel" style="height:4px;"></div>';

    // 斷開舊的 observer
    if (_logsObserver) { _logsObserver.disconnect(); _logsObserver = null; }

    // 載入第一批
    await _fetchMoreLogs(content);

    // 設定 IntersectionObserver：sentinel 進入可見區時觸發下一批
    const sentinel = document.getElementById('logs-sentinel');
    _logsObserver = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && _logsState.hasMore && !_logsState.loading) {
            _fetchMoreLogs(content);
        }
    }, { root: content, rootMargin: '0px 0px 60px 0px', threshold: 0 });
    _logsObserver.observe(sentinel);
}

async function _fetchMoreLogs(content) {
    if (_logsState.loading || !_logsState.hasMore) return;
    _logsState.loading = true;

    // 顯示 loading 提示（插在 sentinel 之前）
    const sentinel = document.getElementById('logs-sentinel');
    const loader   = document.createElement('div');
    loader.id = 'logs-loader';
    loader.style.cssText = 'text-align:center;color:var(--text-secondary);padding:0.4rem;font-size:0.82rem;';
    loader.textContent = '載入中…';
    content.insertBefore(loader, sentinel);

    try {
        const res  = await fetch(`/api/alarm_logs?type=${_logsState.type}&offset=${_logsState.offset}&limit=100`);
        const data = await res.json();

        document.getElementById('logs-loader')?.remove();

        const logsText = document.getElementById('logs-text');
        if (data.logs && data.logs.length > 0) {
            logsText.textContent += data.logs.join('\n') + '\n';
            _logsState.offset  += data.logs.length;
            _logsState.hasMore  = data.has_more;

            // 顯示進度（非最後一批才顯示）
            if (_logsState.hasMore) {
                const hint = document.createElement('div');
                hint.style.cssText = 'text-align:center;color:var(--text-secondary);font-size:0.78rem;padding:0.2rem 0;';
                hint.textContent   = `已載入 ${_logsState.offset} / ${data.total} 筆`;
                content.insertBefore(hint, sentinel);
            }
        } else {
            _logsState.hasMore = false;
            if (_logsState.offset === 0) {
                logsText.textContent = 'No logs available.';
            }
        }
    } catch (e) {
        console.error('Error fetching logs:', e);
        document.getElementById('logs-loader')?.remove();
        const logsText = document.getElementById('logs-text');
        if (_logsState.offset === 0) logsText.textContent = 'Failed to load logs.';
    }

    _logsState.loading = false;
}

function closeLogsModal() {
    if (_logsObserver) { _logsObserver.disconnect(); _logsObserver = null; }
    document.getElementById('logs-modal-overlay').style.display = 'none';
}

document.getElementById('logs-modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('logs-modal-overlay')) closeLogsModal();
});
