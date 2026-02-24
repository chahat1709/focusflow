/**
 * FocusFlow — dashboard_therapeutic.js
 * Main client logic for the therapeutic neurofeedback dashboard.
 * Communicates with the Python backend via HTTP polling.
 */

// ═══════════════════════════════════════════════════════════════
//  CONFIG
// ═══════════════════════════════════════════════════════════════
const API_BASE = '';          // Same origin (served by the Python server)
const POLL_MS = 200;         // Data polling interval
const HISTORY_POINTS = 1500;  // Chart data window (1500 × 0.2s = 300s = full 5-min session)

// ═══════════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════════
const state = {
    connected: false,
    baseline_done: false,
    emg_active: false,
    recording: false,
    sessionStart: null,
    pollTimer: null,
    focus: [],
    alpha: [], beta: [], theta: [], delta: [], gamma: [],
    gyroX: [], gyroY: [],
    timestamps: [],
    sessionHistory: JSON.parse(localStorage.getItem('ff_sessions') || '[]'),
    settings: JSON.parse(localStorage.getItem('ff_settings') || '{}'),
    activeStudent: null, // Phase 2: Currently selected student for session
    _alertTimer: null, // Internal timer for alerts
};

// ═══════════════════════════════════════════════════════════════
//  DOM REFS
// ═══════════════════════════════════════════════════════════════
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ═══════════════════════════════════════════════════════════════
//  TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════
// Toggle Sidebar Animation
function toggleSidebar() {
    const container = document.querySelector('.app-container');
    container.classList.toggle('collapsed');
}
window.toggleSidebar = toggleSidebar;

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const panel = document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`);
        if (panel) panel.classList.add('active');
    });
});

// ═══════════════════════════════════════════════════════════════
//  CHARTS  (Chart.js)
// ═══════════════════════════════════════════════════════════════
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 150 },
    plugins: { legend: { labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 } } } },
    scales: {
        x: { display: false },
        y: { ticks: { color: '#64748B', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
    }
};

let focusChart, spectrumChart, gyroChart, historyChart;

function initCharts() {
    // EEG Frequency Bands (live line chart)
    const fcCtx = $('focusChart');
    if (fcCtx) {
        focusChart = new Chart(fcCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Alpha', data: [], borderColor: '#2DD4BF', backgroundColor: 'rgba(45,212,191,0.1)', borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true },
                    { label: 'Beta', data: [], borderColor: '#7DD3FC', backgroundColor: 'rgba(125,211,252,0.1)', borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true },
                    { label: 'Theta', data: [], borderColor: '#FCD34D', backgroundColor: 'rgba(252,211,77,0.05)', borderWidth: 1.5, tension: 0.4, pointRadius: 0, fill: false },
                    { label: 'Delta', data: [], borderColor: '#A78BFA', backgroundColor: 'rgba(167,139,250,0.05)', borderWidth: 1.5, tension: 0.4, pointRadius: 0, fill: false },
                    { label: 'Gamma', data: [], borderColor: '#F472B6', backgroundColor: 'rgba(244,114,182,0.05)', borderWidth: 1.5, tension: 0.4, pointRadius: 0, fill: false },
                ]
            },
            options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, max: 1 } } }
        });
    }

    // Spectral Power (bar chart)
    const spCtx = $('spectrumChart');
    if (spCtx) {
        spectrumChart = new Chart(spCtx, {
            type: 'bar',
            data: {
                labels: ['Delta', 'Theta', 'Alpha', 'Beta', 'Gamma'],
                datasets: [{
                    data: [0, 0, 0, 0, 0],
                    backgroundColor: ['#A78BFA', '#FCD34D', '#2DD4BF', '#7DD3FC', '#F472B6'],
                    borderRadius: 8,
                    barThickness: 40,
                }]
            },
            options: {
                ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: false } },
                scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, max: 1 } }
            }
        });
    }

    // Gyro (simple line)
    const gyCtx = $('gyroChart');
    if (gyCtx) {
        gyroChart = new Chart(gyCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'Pitch', data: [], borderColor: '#2DD4BF', borderWidth: 1.5, tension: 0.4, pointRadius: 0 },
                    { label: 'Roll', data: [], borderColor: '#F472B6', borderWidth: 1.5, tension: 0.4, pointRadius: 0 },
                ]
            },
            options: chartDefaults
        });
    }

    // Session History (bar chart, analytics tab)
    const hcCtx = $('historyChart');
    if (hcCtx) {
        historyChart = new Chart(hcCtx, {
            type: 'bar',
            data: {
                labels: state.sessionHistory.slice(-10).map((_, i) => `#${i + 1}`),
                datasets: [{
                    label: 'Avg Focus %',
                    data: state.sessionHistory.slice(-10).map(s => s.avgFocus || 0),
                    backgroundColor: 'rgba(45,212,191,0.4)',
                    borderColor: '#2DD4BF',
                    borderWidth: 1,
                    borderRadius: 8,
                }]
            },
            options: { ...chartDefaults, scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, max: 100 } } }
        });
    }

    updateAnalytics();
}

// ═══════════════════════════════════════════════════════════════
//  CONNECTION  (via backend API)
// ═══════════════════════════════════════════════════════════════
const $indicator = $('statusIndicator');
const $statusText = $('statusText');
const $connectBtn = $('scanBtn'); // Map scanBtn (sidebar) to the connection logic
const $statusMsg = $('statusMessage');
const $sidebarSt = $('sidebarStatus');

function updateConnectionUI(s, msg = '') {
    if ($indicator) $indicator.className = s;
    switch (s) {
        case 'idle':
            if ($statusText) $statusText.textContent = 'Ready';
            if ($connectBtn) { $connectBtn.textContent = 'Connect Muse'; $connectBtn.disabled = false; }
            if ($statusMsg) $statusMsg.textContent = '';
            if ($sidebarSt) { $sidebarSt.textContent = 'OFFLINE'; $sidebarSt.className = 'status-text offline'; }
            break;
        case 'scanning':
            if ($statusText) $statusText.textContent = 'Scanning...';
            if ($connectBtn) { $connectBtn.textContent = 'Searching...'; $connectBtn.disabled = true; }
            if ($statusMsg) $statusMsg.textContent = 'Looking for Muse headband via Bluetooth...';
            if ($sidebarSt) { $sidebarSt.textContent = 'SCANNING'; $sidebarSt.className = 'status-text offline'; }
            break;
        case 'connected':
            if ($statusText) $statusText.textContent = 'Connected';
            if ($connectBtn) { $connectBtn.textContent = 'Disconnect'; $connectBtn.disabled = false; }
            if ($statusMsg) $statusMsg.textContent = '✓ Live EEG data streaming';
            if ($sidebarSt) { $sidebarSt.textContent = 'LIVE'; $sidebarSt.className = 'status-text online'; }
            state.connected = true;
            startPolling();
            break;
        case 'simulating':
            if ($statusText) $statusText.textContent = 'Demo Mode';
            if ($connectBtn) { $connectBtn.textContent = 'Stop Demo'; $connectBtn.disabled = false; }
            if ($statusMsg) $statusMsg.textContent = '⚠ Simulated data (not live)';
            if ($sidebarSt) { $sidebarSt.textContent = 'DEMO'; $sidebarSt.className = 'status-text offline'; }
            state.connected = true;
            startPolling();
            break;
        case 'error':
            if ($statusText) $statusText.textContent = 'Not Found';
            if ($connectBtn) { $connectBtn.textContent = 'Try Again'; $connectBtn.disabled = false; }
            if ($statusMsg) $statusMsg.textContent = msg || '✗ Turn on your Muse 2 and try again';
            if ($sidebarSt) { $sidebarSt.textContent = 'ERROR'; $sidebarSt.className = 'status-text offline'; }
            break;
    }
}

// Connect button handler
if ($connectBtn) {
    $connectBtn.addEventListener('click', async () => {
        if (state.connected) {
            try { await fetch(`${API_BASE}/api/system/disconnect`, { method: 'POST' }); } catch (e) { }
            state.connected = false;
            stopPolling();
            updateConnectionUI('idle');
        } else {
            updateConnectionUI('scanning');
            try {
                const res = await fetch(`${API_BASE}/api/system/connect`, { method: 'POST' });
                const data = await res.json();
                if (data.status === 'scanning' || data.status === 'ok') {
                    startStatusPolling();
                }
            } catch (err) {
                updateConnectionUI('error', 'Backend not responding');
            }
        }
    });
}

// Sidebar scan button - redundant now but kept for safety
const $scanBtn = $('scanBtn');
// Already handled by mapping $connectBtn to scanBtn

let statusPollTimer = null;
function startStatusPolling() {
    if (statusPollTimer) clearInterval(statusPollTimer);
    statusPollTimer = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/system/status`);
            const data = await res.json();
            const cs = data.connection_state || 'idle';
            if (cs === 'connected') {
                updateConnectionUI('connected');
                clearInterval(statusPollTimer); statusPollTimer = null;
            } else if (cs === 'simulating') {
                updateConnectionUI('simulating');
                clearInterval(statusPollTimer); statusPollTimer = null;
            } else if (cs === 'error') {
                updateConnectionUI('error', 'Muse 2 not found — make sure it is turned on and nearby');
                clearInterval(statusPollTimer); statusPollTimer = null;
            }
        } catch (e) { }
    }, 1000);
}

// ═══════════════════════════════════════════════════════════════
// --- UI FEEDBACK HELPERS ---
function showAlert(msg, type = 'warn', duration = 4000) {
    const $b = $('alertBanner');
    const $m = $('alertMessage');
    const $i = $('alertIcon');
    if (!$b || !$m) return;

    $m.textContent = msg;
    $i.textContent = type === 'error' ? '❌' : (type === 'success' ? '✅' : '⚠️');
    $b.className = type;
    $b.style.display = 'flex';

    if (state._alertTimer) clearTimeout(state._alertTimer);
    state._alertTimer = setTimeout(() => {
        $b.style.display = 'none';
    }, duration);
}

function updateElectrodeMap(diagnostics) {
    if (!diagnostics || !state.connected) {
        document.querySelectorAll('.sensor-node').forEach(n => n.className = 'sensor-node off');
        $('mapStatus').textContent = 'Headset Offline';
        return;
    }

    const sensors = ['TP9', 'AF7', 'AF8', 'TP10'];
    let allPass = true;

    sensors.forEach(ch => {
        const node = $('node-' + ch);
        if (!node) return;

        const s = (diagnostics.eeg && diagnostics.eeg[ch]) ? diagnostics.eeg[ch].status : 'OFF';
        node.className = 'sensor-node ' + s.toLowerCase();
        if (s !== 'PASS') allPass = false;
    });

    const $ms = $('mapStatus');
    if (allPass) {
        $ms.textContent = 'Perfect Fit';
        $ms.style.color = 'var(--healing-sage)';
    } else {
        $ms.textContent = 'Adjust Sensors';
        $ms.style.color = 'var(--warm-sand)';
    }
}
// ═══════════════════════════════════════════════════════════════
//  DATA POLLING
// ═══════════════════════════════════════════════════════════════
function startPolling() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(pollServer, POLL_MS);
}

function stopPolling() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

async function pollServer() {
    try {
        const res = await fetch(`${API_BASE}/api/focus`);
        const d = await res.json();

        state.baseline_done = d.baseline_done;

        // Update Signal Quality Map
        // We fetch diagnostics every few polls or include it in snapshot
        // For simplicity, let's use the sensor_test endpoint if needed, but 
        // production_server.py now returns a good enough summary for basic maps.
        updateElectrodeMap(d.diagnostics);

        // Handle EMG Noise (Muscle Tension)
        if (d.emg_noise && !state.emg_active) {
            showAlert('High Muscle Noise: Please relax your jaw', 'warn');
            state.emg_active = true;
        } else if (!d.emg_noise) {
            state.emg_active = false;
        }

        // Focus value
        const $fv = $('focusValue');
        const $fl = $('focusLabel');
        if ($fv) {
            if (d.headband_on === false && state.connected) {
                // Headband removed — show clear warning
                $fv.innerHTML = `<span style="font-size:16px;color:#FCD34D">⚠ Off</span>`;
                if ($fl) $fl.textContent = 'Put headband on head';
            } else if (d.baseline_done === false && state.connected) {
                $fv.innerHTML = `<span style="font-size:18px;color:var(--text-secondary)">Learning...</span>`;
                if ($fl) $fl.textContent = 'Calibrating baseline (15s)';
            } else {
                const fp = Math.round((d.focus || 0) * 100);
                $fv.innerHTML = `${fp}<span class="card-unit">%</span>`;
                state.focus.push(d.focus || 0);
                // Show dominant band
                if ($fl) {
                    const bands = { Alpha: d.alpha, Beta: d.beta, Theta: d.theta, Delta: d.delta, Gamma: d.gamma };
                    const dominant = Object.entries(bands).sort((a, b) => b[1] - a[1])[0];
                    $fl.textContent = `${dominant[0]} Dominant`;
                }
            }
        }

        // Signal quality bars
        updateSensorBars(d.signal_ok);

        // Push history
        const now = Date.now();
        // focus pushed above based on baseline
        state.alpha.push(d.alpha || 0);
        state.beta.push(d.beta || 0);
        state.theta.push(d.theta || 0);
        state.delta.push(d.delta || 0);
        state.gamma.push(d.gamma || 0);
        state.timestamps.push(now);

        // Trim to window
        while (state.focus.length > HISTORY_POINTS) {
            state.focus.shift(); state.alpha.shift(); state.beta.shift();
            state.theta.shift(); state.delta.shift(); state.gamma.shift();
            state.timestamps.shift();
        }

        // Update live charts
        updateLiveCharts();

        // Mind State (Muse-style: Calm / Neutral / Active) — from server
        const $vv = $('valenceValue');
        const $vl = $('valenceLabel');
        if ($vv && $vl) {
            const ms = d.mind_state || 'unknown';
            const msTime = Math.floor(d.mind_state_time || 0);
            const mins = Math.floor(msTime / 60);
            const secs = msTime % 60;
            const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

            if (ms === 'calm') {
                $vv.textContent = '🧘';
                $vv.style.color = '#86EFAC';
                $vl.textContent = 'Calm';
                $vl.style.color = '#86EFAC';
            } else if (ms === 'active') {
                $vv.textContent = '⚡';
                $vv.style.color = '#7DD3FC';
                $vl.textContent = 'Active';
                $vl.style.color = '#7DD3FC';
            } else if (ms === 'neutral') {
                $vv.textContent = '🎯';
                $vv.style.color = '#FCD34D';
                $vl.textContent = 'Neutral';
                $vl.style.color = '#FCD34D';
            } else if (ms === 'calibrating') {
                $vv.textContent = '⏳';
                $vv.style.color = '#94A3B8';
                $vl.textContent = 'Calibrating...';
                $vl.style.color = '#94A3B8';
            } else {
                $vv.textContent = '--';
                $vv.style.color = '#64748B';
                $vl.textContent = 'No data';
                $vl.style.color = '#64748B';
            }
        }

        // ══════════════════════════════════════════════════
        // HEADBAND-OFF GATE: Block ALL fake data (like Muse app)
        // ══════════════════════════════════════════════════
        if (d.headband_on === false && state.connected) {
            // Focus card: show warning
            if ($fv) $fv.innerHTML = `<span style="font-size:16px;color:#FCD34D">⚠ Off</span>`;
            if ($fl) $fl.textContent = 'Put headband on head';

            // BPM: clear
            const $bpm = $('bpmValue');
            if ($bpm) $bpm.innerHTML = `--<span class="card-unit">BPM</span>`;

            // Blink/Fatigue: clear
            const $fatigue = $('blinkValue');
            if ($fatigue) $fatigue.innerHTML = `--<span class="card-unit">/min</span>`;

            // Valence: clear
            const $vv = $('valenceValue');
            if ($vv) $vv.textContent = '--';
            const $vl = $('valenceLabel');
            if ($vl) $vl.textContent = 'No contact';

            // Badge: HEADBAND OFF
            const badge = $('neuroStateBadge');
            if (badge) {
                badge.style.display = 'inline-block';
                badge.textContent = 'HEADBAND OFF';
                badge.style.borderColor = '#EF4444';
                badge.style.color = '#EF4444';
            }

            // Signal bars: poor
            updateSensorBars(false);

            // DON'T push chart data — no fake band powers
            return;
        }

        // ══════════════════════════════════════════════════
        // Below: headband IS on — normal data flow
        // ══════════════════════════════════════════════════

        // Heart Rate (BPM)
        if (d.bpm !== undefined) {
            const $bpm = $('bpmValue');
            if ($bpm) {
                $bpm.innerHTML = d.bpm > 0 ? `${d.bpm}<span class="card-unit">BPM</span>` : `--<span class="card-unit">BPM</span>`;
            }
        }

        // Fatigue Index (Blink Rate)
        const $fatigue = $('blinkValue');
        if ($fatigue) {
            $fatigue.innerHTML = `${d.blink_rate || 0}<span class="card-unit">/min</span>`;
        }

        // Accel/Gyro
        if (d.gyro) {
            state.gyroX.push(d.gyro.x || 0);
            state.gyroY.push(d.gyro.y || 0);
        } else {
            state.gyroX.push(0); state.gyroY.push(0);
        }
        while (state.gyroX.length > HISTORY_POINTS) { state.gyroX.shift(); state.gyroY.shift(); }

        // Neuro-state badge: show RAW focus % (precision mode)
        const badge = $('neuroStateBadge');
        if (badge && state.connected) {
            badge.style.display = 'inline-block';
            if (d.baseline_done === false) {
                badge.textContent = 'CALIBRATING';
                badge.style.borderColor = '#7DD3FC';
                badge.style.color = '#7DD3FC';
            } else {
                const fp = Math.round((d.focus || 0) * 100);
                badge.textContent = `FOCUS ${fp}%`;
                if (fp >= 70) {
                    badge.style.borderColor = '#86EFAC'; badge.style.color = '#86EFAC';
                } else if (fp >= 40) {
                    badge.style.borderColor = '#2DD4BF'; badge.style.color = '#2DD4BF';
                } else {
                    badge.style.borderColor = '#FCD34D'; badge.style.color = '#FCD34D';
                }
            }
        }

    } catch (err) {
        // Count consecutive errors — only shut down after 10 in a row (~2s)
        if (!state._pollErrors) state._pollErrors = 0;
        state._pollErrors++;
        if (state._pollErrors >= 10) {
            state.connected = false;
            stopPolling();
            updateConnectionUI('error', 'Server disconnected');
        }
        return;  // Don't crash — just skip this poll cycle
    }
    // Reset error counter on success
    state._pollErrors = 0;
}

function updateSensorBars(signalOk) {
    for (let i = 0; i < 4; i++) {
        const bar = $(`sensor-${i}`);
        if (bar) {
            bar.className = 'signal-bar ' + (signalOk ? 'good' : 'poor');
        }
    }
}

function updateLiveCharts() {
    if (focusChart) {
        const labels = state.timestamps.map((_, i) => i);
        focusChart.data.labels = labels;
        focusChart.data.datasets[0].data = state.alpha;
        focusChart.data.datasets[1].data = state.beta;
        focusChart.data.datasets[2].data = state.theta;
        focusChart.data.datasets[3].data = state.delta;
        focusChart.data.datasets[4].data = state.gamma;
        focusChart.update('none');
    }

    if (spectrumChart && state.alpha.length > 0) {
        const last = state.alpha.length - 1;
        spectrumChart.data.datasets[0].data = [
            state.delta[last], state.theta[last], state.alpha[last],
            state.beta[last], state.gamma[last]
        ];
        spectrumChart.update('none');
    }

    // Real Gyro Data
    if (gyroChart) {
        gyroChart.data.labels = state.gyroX.map((_, i) => i);
        gyroChart.data.datasets[0].data = state.gyroX; // Pitch
        gyroChart.data.datasets[1].data = state.gyroY; // Roll
        gyroChart.update('none');
    }
}

// ═══════════════════════════════════════════════════════════════
//  SESSION RECORDING  (5-minute timed session with auto-stop)
// ═══════════════════════════════════════════════════════════════
const SESSION_DURATION_SEC = 300; // 5 minutes
let sessionCountdownTimer = null;
let sessionRemainingSeconds = 0;

function _startSessionInternal() {
    if (state.recording) {
        endSession();
        return;
    }
    // Block session if Muse is not connected
    if (!state.connected) {
        showAlert('Connect the Muse headband first before starting a session.', 'error', 4000);
        return;
    }
    state.recording = true;
    state.sessionStart = Date.now();
    state.focus = []; state.alpha = []; state.beta = [];
    state.theta = []; state.delta = []; state.gamma = [];

    // Start countdown
    sessionRemainingSeconds = SESSION_DURATION_SEC;
    updateSessionTimerUI();
    sessionCountdownTimer = setInterval(() => {
        sessionRemainingSeconds--;
        updateSessionTimerUI();
        if (sessionRemainingSeconds <= 0) {
            endSession();
        }
    }, 1000);

    const btn = document.getElementById('stopSessionBtn');
    if (btn) btn.style.display = 'inline-block';
}

function startSession() {
    // If there's an active student, do the student flow (baseline reset etc)
    if (state.activeStudent) {
        startSessionWithStudent();
        return;
    }
    // Otherwise, just start a plain recording
    _startSessionInternal();
}

function endSession() {
    state.recording = false;

    // Stop countdown timer
    if (sessionCountdownTimer) {
        clearInterval(sessionCountdownTimer);
        sessionCountdownTimer = null;
    }

    const duration = Date.now() - state.sessionStart;
    const avgFocus = state.focus.length > 0 ? Math.round((state.focus.reduce((a, b) => a + b, 0) / state.focus.length) * 100) : 0;
    const peakFocus = state.focus.length > 0 ? Math.round(Math.max(...state.focus) * 100) : 0;

    const session = {
        date: new Date().toISOString(),
        duration: Math.round(duration / 1000),
        avgFocus,
        samples: state.focus.length,
    };
    state.sessionHistory.push(session);
    localStorage.setItem('ff_sessions', JSON.stringify(state.sessionHistory));
    updateAnalytics();

    // Phase 2: Save to Supabase if student is active
    if (state.activeStudent) {
        console.log("Saving session to Supabase for:", state.activeStudent.name);
        fetch(`${API_BASE}/api/session/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: state.activeStudent.id,
                duration: session.duration,
                avg_focus: avgFocus,
                peak_focus: peakFocus,
                graph_data: state.focus.slice(-1000)
            })
        }).then(r => r.json()).then(res => {
            console.log("Supabase save result:", res);
            showAlert(`✅ Session saved for ${state.activeStudent.name} — ${avgFocus}% avg focus`, 'info', 5000);
        }).catch(err => console.error("Supabase link error:", err));
    }

    const btn = document.getElementById('stopSessionBtn');
    if (btn) btn.style.display = 'none';

    // Reset timer display
    const timerEl = document.getElementById('sessionCountdown');
    if (timerEl) timerEl.textContent = '05:00';

    // Keep activeStudent for back-to-back sessions; only hide UI indicator
    hideActiveStudentUI();
}

function updateSessionTimerUI() {
    const min = Math.floor(sessionRemainingSeconds / 60);
    const sec = sessionRemainingSeconds % 60;
    const display = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;

    let timerEl = document.getElementById('sessionCountdown');
    if (!timerEl) {
        // Create the timer element next to the REC button
        const controls = document.querySelector('.session-controls');
        if (controls) {
            timerEl = document.createElement('div');
            timerEl.id = 'sessionCountdown';
            timerEl.style.cssText = "font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:var(--therapeutic-teal);letter-spacing:2px;min-width:70px;text-align:center;";
            controls.prepend(timerEl);
        }
    }
    if (timerEl) {
        timerEl.textContent = display;
        // Flash red in last 30 seconds
        if (sessionRemainingSeconds <= 30) {
            timerEl.style.color = '#EF4444';
            timerEl.style.animation = 'pulse-red 1s infinite';
        } else {
            timerEl.style.color = 'var(--therapeutic-teal)';
            timerEl.style.animation = 'none';
        }
    }
}

function updateAnalytics() {
    const $ts = $('totalSessions');
    const $af = $('avgFocus');
    if ($ts) $ts.textContent = state.sessionHistory.length;
    if ($af) {
        const avg = state.sessionHistory.length > 0
            ? Math.round(state.sessionHistory.reduce((a, s) => a + (s.avgFocus || 0), 0) / state.sessionHistory.length)
            : 0;
        $af.innerHTML = `${avg}<span class="card-unit">%</span>`;
    }
    if (historyChart) {
        const last10 = state.sessionHistory.slice(-10);
        historyChart.data.labels = last10.map((_, i) => `#${i + 1}`);
        historyChart.data.datasets[0].data = last10.map(s => s.avgFocus || 0);
        historyChart.update();
    }
}

// ═══════════════════════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════════════════════
function saveSettings() {
    const apiKey = $('apiKeyInput')?.value || '';
    const notch = $('notchSelect')?.value || '50';
    state.settings = { apiKey, notch };
    localStorage.setItem('ff_settings', JSON.stringify(state.settings));
    // Notify backend of notch filter change
    fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notch })
    }).catch(() => { });
}

function loadSettings() {
    if (state.settings.apiKey) { const $ak = $('apiKeyInput'); if ($ak) $ak.value = state.settings.apiKey; }
    if (state.settings.notch) { const $ns = $('notchSelect'); if ($ns) $ns.value = state.settings.notch; }
}

// ═══════════════════════════════════════════════════════════════
//  CALIBRATION
// ═══════════════════════════════════════════════════════════════
let calibTimer = null;
function startCalibration() {
    const overlay = $('calibrationOverlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    let progress = 0;
    const bar = $('calibProgress');
    calibTimer = setInterval(() => {
        progress += (100 / 60); // 30 seconds ≈ 60 ticks at 500ms
        if (bar) bar.style.width = Math.min(progress, 100) + '%';
        if (progress >= 100) {
            clearInterval(calibTimer);
            overlay.style.display = 'none';
            // Send calibration complete to backend
            fetch(`${API_BASE}/api/calibrate`, { method: 'POST' }).catch(() => { });
        }
    }, 500);
}

function cancelCalibration() {
    if (calibTimer) clearInterval(calibTimer);
    const overlay = $('calibrationOverlay');
    if (overlay) overlay.style.display = 'none';
}

// ═══════════════════════════════════════════════════════════════
//  MODAL
// ═══════════════════════════════════════════════════════════════
function closeModal() {
    const m = $('scanModal');
    if (m) m.classList.remove('active');
}

// ═══════════════════════════════════════════════════════════════
//  3D NEURAL BACKGROUND  (Three.js particle sphere)
// ═══════════════════════════════════════════════════════════════
function initNeuralBackground() {
    const canvas = $('neuralCanvas');
    if (!canvas || typeof THREE === 'undefined') return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Particle sphere
    const count = 800;
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = 2 * Math.PI * Math.random();
        const r = 3 + Math.random() * 0.5;
        pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        pos[i * 3 + 2] = r * Math.cos(phi);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));

    const mat = new THREE.PointsMaterial({ color: 0x2DD4BF, size: 0.03, transparent: true, opacity: 0.6 });
    const points = new THREE.Points(geo, mat);
    scene.add(points);

    camera.position.z = 6;

    function animate() {
        requestAnimationFrame(animate);
        points.rotation.y += 0.001;
        points.rotation.x += 0.0005;
        renderer.render(scene, camera);
    }
    animate();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}

// ═══════════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initNeuralBackground();
    loadSettings();
    updateConnectionUI('idle');

    // Auto-try connect to backend on load
    setTimeout(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/system/status`);
            const data = await res.json();
            if (data.connection_state === 'connected') {
                updateConnectionUI('connected');
            }
        } catch (e) { }
    }, 500);
});

// Make functions globally accessible for inline onclick handlers
window.startSession = startSession;
window.saveSettings = saveSettings;
window.startCalibration = startCalibration;
window.cancelCalibration = cancelCalibration;
window.closeModal = closeModal;

// ═══════════════════════════════════════════════════════════════
//  SENSOR TEST POLLING
// ═══════════════════════════════════════════════════════════════
let sensorTestTimer = null;

function startSensorTest() {
    if (sensorTestTimer) return;
    sensorTestTimer = setInterval(pollSensorTest, 500);
    pollSensorTest(); // immediate first poll
}

function stopSensorTest() {
    if (sensorTestTimer) { clearInterval(sensorTestTimer); sensorTestTimer = null; }
}

async function pollSensorTest() {
    try {
        const res = await fetch(`${API_BASE}/api/sensor_test`);
        const d = await res.json();

        // Overall status
        const el = document.getElementById('sensorTestStatus');
        if (!d.connected) {
            el.textContent = '⚠️ Device not connected. Click "Connect Sensor" in the sidebar.';
            el.style.color = '#FBBF24';
        } else {
            const eegStatuses = Object.values(d.eeg).map(c => c.status);
            const allPass = eegStatuses.every(s => s === 'PASS');
            const anyFail = eegStatuses.some(s => s === 'FAIL');
            if (allPass) {
                el.textContent = '✅ All EEG sensors are working perfectly!';
                el.style.color = '#2DD4BF';
            } else if (anyFail) {
                el.textContent = '❌ Some sensors have poor contact. Adjust the headset.';
                el.style.color = '#EF4444';
            } else {
                el.textContent = '⏳ Sensors receiving data... checking quality...';
                el.style.color = '#FBBF24';
            }
        }

        // EEG Channels
        for (const [ch, info] of Object.entries(d.eeg)) {
            const card = document.getElementById(`sensor${ch}`);
            const dot = card?.querySelector('.sensor-status-dot');
            if (!card || !dot) continue;

            // Status dot
            dot.className = 'sensor-status-dot ' + info.status.toLowerCase().replace('no_data', 'no-data');

            // Card border
            card.className = 'sensor-card ' + (info.status === 'PASS' ? 'pass' : info.status === 'WARN' ? 'warn' : info.status === 'FAIL' ? 'fail' : '');

            // Stats
            const ampEl = document.getElementById(`amp${ch}`);
            const noiseEl = document.getElementById(`noise${ch}`);
            const p2pEl = document.getElementById(`p2p${ch}`);
            if (ampEl) ampEl.textContent = info.amplitude || '--';
            if (noiseEl) noiseEl.textContent = info.noise || '--';
            if (p2pEl) p2pEl.textContent = info.peak_to_peak || '--';

            updateElectrodeMap(d);

            // Waveform
            drawWaveform(`wave${ch}`, info.waveform, info.status);
        }

        // PPG
        const ppgDot = document.getElementById('ppgDot');
        const ppgBPM = document.getElementById('ppgBPM');
        const ppgStatus = document.getElementById('ppgStatus');
        if (ppgDot) ppgDot.className = 'sensor-status-dot ' + d.ppg.status.toLowerCase().replace('no_data', 'no-data');
        if (ppgBPM) ppgBPM.textContent = d.ppg.bpm > 0 ? `${d.ppg.bpm} BPM` : '-- BPM';
        if (ppgStatus) ppgStatus.textContent = d.ppg.status === 'PASS' ? '✅ Active' : 'Waiting...';

        // Accelerometer
        const accelDot = document.getElementById('accelDot');
        if (accelDot) accelDot.className = 'sensor-status-dot ' + d.accelerometer.status.toLowerCase().replace('no_data', 'no-data');
        const ax = document.getElementById('accelX');
        const ay = document.getElementById('accelY');
        const az = document.getElementById('accelZ');
        if (ax) ax.textContent = d.accelerometer.x;
        if (ay) ay.textContent = d.accelerometer.y;
        if (az) az.textContent = d.accelerometer.z;

        // Gyroscope
        const gyroDot = document.getElementById('gyroDot');
        if (gyroDot) gyroDot.className = 'sensor-status-dot ' + d.gyroscope.status.toLowerCase().replace('no_data', 'no-data');
        const gx = document.getElementById('gyroX2');
        const gy = document.getElementById('gyroY2');
        const gz = document.getElementById('gyroZ2');
        if (gx) gx.textContent = d.gyroscope.x;
        if (gy) gy.textContent = d.gyroscope.y;
        if (gz) gz.textContent = d.gyroscope.z;

        // IAF
        const iafEl = document.getElementById('iafDisplay');
        if (iafEl) {
            if (d.iaf) {
                iafEl.innerHTML = `<b style="color:var(--therapeutic-teal);font-size:18px;">${d.iaf.toFixed(1)} Hz</b> — Your personal alpha peak. Band boundaries are customized to your brain.`;
            } else {
                iafEl.textContent = 'Not yet calibrated. Run a session to detect your IAF.';
            }
        }
    } catch (e) { /* backend not ready */ }
}

function drawWaveform(canvasId, data, status) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Color based on status
    const colors = { PASS: '#2DD4BF', WARN: '#FBBF24', FAIL: '#EF4444', NO_DATA: '#475569' };
    const color = colors[status] || '#475569';

    // Scale data
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';

    for (let i = 0; i < data.length; i++) {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((data[i] - min) / range) * (h - 4) - 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Glow effect
    ctx.globalAlpha = 0.15;
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.globalAlpha = 1.0;
}

// Hook into tab switching to start/stop sensor test
const origTabHandler = document.querySelectorAll('.tab-btn');
origTabHandler.forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.dataset.tab === 'sensortest') {
            startSensorTest();
        } else {
            stopSensorTest();
        }
    });
});
// ═══════════════════════════════════════════════════════════════
//  PHASE 2: STUDENT MANAGEMENT (Student Panel)
// ═══════════════════════════════════════════════════════════════

function showSPPanel(type) {
    $$('.sp-panel').forEach(p => p.style.display = 'none');
    $$('.sp-card').forEach(c => c.classList.remove('active'));
    $(`sp_${type}`).style.display = 'block';
    $(`spCard_${type}`).classList.add('active');

    if (type === 'college') loadColleges();
    if (type === 'class') loadCollegesForDropdown('sel_clg_for_class');
    if (type === 'student') loadCollegesForDropdown('sel_clg_for_student');
}

async function createCollege() {
    const name = $('inp_clg_name').value;
    const city = $('inp_clg_city').value;
    const board = $('inp_clg_board').value;
    if (!name) return alert("Please enter college name");

    const res = await fetch(`${API_BASE}/api/college/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, city, board })
    });
    const d = await res.json();
    if (d.status === 'ok') {
        $('inp_clg_name').value = '';
        $('inp_clg_city').value = '';
        $('inp_clg_board').value = '';
        loadColleges();
    }
}

async function loadColleges() {
    const res = await fetch(`${API_BASE}/api/colleges`);
    const data = await res.json();
    const list = $('list_colleges');
    list.innerHTML = data.map(c => `
        <div class="sp-item">
            <div><strong>${c.name}</strong> <small style="opacity:0.6;margin-left:8px;">${c.city}</small></div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="font-size:10px;background:rgba(255,255,255,0.1);padding:2px 8px;border-radius:10px;">${c.board}</div>
                <button onclick="deleteCollege('${c.id}','${(c.name || '').replace(/'/g, '')}')"
                    style="font-size:10px;background:#EF4444;color:white;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;"
                    title="Delete college">🗑️</button>
            </div>
        </div>
    `).join('') || '<div style="opacity:0.5;text-align:center;padding:20px;">No colleges found</div>';
}

async function loadCollegesForDropdown(id) {
    const res = await fetch(`${API_BASE}/api/colleges`);
    const data = await res.json();
    const sel = $(id);
    sel.innerHTML = '<option value="">Select College...</option>' +
        data.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

async function createClass() {
    const cid = $('sel_clg_for_class').value;
    const name = $('inp_class_name').value;
    if (!cid || !name) return alert("Select college and enter class name");

    const res = await fetch(`${API_BASE}/api/class/add`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ college_id: cid, name })
    });
    if ((await res.json()).status === 'ok') {
        $('inp_class_name').value = '';
        loadClasses(cid);
    }
}

async function loadClasses(cid) {
    const res = await fetch(`${API_BASE}/api/classes?college_id=${cid}`);
    const data = await res.json();
    $('list_classes').innerHTML = data.map(c => `
        <div class="sp-item">
            <div>${c.name}</div>
            <button onclick="deleteClass('${c.id}','${(c.name || '').replace(/'/g, '')}','${cid}')"
                style="font-size:10px;background:#EF4444;color:white;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;"
                title="Delete class">🗑️</button>
        </div>
    `).join('');
}

async function loadClassesForStudent() {
    const cid = $('sel_clg_for_student').value;
    if (!cid) return;
    const res = await fetch(`${API_BASE}/api/classes?college_id=${cid}`);
    const data = await res.json();
    $('sel_class_for_student').innerHTML = '<option value="">Select Class...</option>' +
        data.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

async function createStudent() {
    const class_id = $('sel_class_for_student').value;
    const name = $('inp_stu_name').value;
    const roll_no = $('inp_stu_roll').value;
    const age = $('inp_stu_age').value;
    const notes = $('inp_stu_notes').value;
    if (!class_id || !name) return alert("Select class and enter name");

    const res = await fetch(`${API_BASE}/api/student/add`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ class_id, name, roll_no, age, notes })
    });
    if ((await res.json()).status === 'ok') {
        $('inp_stu_name').value = ''; $('inp_stu_roll').value = '';
        loadStudents(class_id);
    }
}

async function loadStudents(class_id) {
    const res = await fetch(`${API_BASE}/api/students?class_id=${class_id}`);
    const data = await res.json();
    // Get college/class names from the current dropdown selections for context
    const clgSel = $('sel_clg_for_student');
    const clsSel = $('sel_class_for_student');
    const clgName = clgSel ? (clgSel.options[clgSel.selectedIndex]?.text || '') : '';
    const clsName = clsSel ? (clsSel.options[clsSel.selectedIndex]?.text || '') : '';
    $('list_students').innerHTML = data.map(s => {
        const safeName = (s.name || '').replace(/'/g, '');
        return `
        <div class="sp-item">
            <div>${s.name} <small>(${s.roll_no})</small></div>
            <div style="display:flex;gap:6px;">
                <button onclick="openModalForStudent('${s.id}', '${safeName}', '${clsName.replace(/'/g, '')}', '${clgName.replace(/'/g, '')}')" style="font-size:10px;background:var(--therapeutic-teal);color:#0A2E4D;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;">Session</button>
                <button onclick="deleteStudent('${s.id}','${safeName}','${class_id}')"
                    style="font-size:10px;background:#EF4444;color:white;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;"
                    title="Delete student">🗑️</button>
            </div>
        </div>
    `;
    }).join('');
}

// ═══════════════════════════════════════════════════════════════
//  PHASE 2: DATABASE SEARCH
// ═══════════════════════════════════════════════════════════════

async function dbSearch() {
    const clg = $('db_search_college').value;
    const cls = $('db_search_class').value;
    const name = $('db_search_name').value;

    if (!clg && !cls && !name) {
        loadRecentSessions(); // Auto-load recent if search is cleared
        return;
    }

    const res = await fetch(`${API_BASE}/api/students/search?college=${clg}&class_name=${cls}&name=${name}`);
    const results = await res.json();

    $('dbResults').innerHTML = results.map(s => `
        <div class="db-result-card">
            <div>
                <div style="font-weight:600;font-size:16px;">${s.name}</div>
                <div style="font-size:12px;color:var(--text-secondary);">${s.class_name} — ${s.college_name}</div>
            </div>
            <div style="display:flex;gap:12px;">
                <button onclick="downloadReport('${s.id}', '${s.name}', '${s.roll_no}', '${s.age}', '${s.class_name}', '${s.college_name}')" class="btn-db-action">📄 Report</button>
                <button onclick="openModalForStudent('${s.id}', '${s.name}', '${s.class_name}', '${s.college_name}')" class="btn-db-action active">▶ New Session</button>
                <button onclick="deleteStudent('${s.id}','${(s.name || '').replace(/'/g, '')}')" class="btn-db-action" style="background:rgba(239,68,68,0.2);color:#EF4444;">🗑️ Delete</button>
            </div>
        </div>
    `).join('') || '<div style="opacity:0.5;text-align:center;padding:40px;">No students found matching search.</div>';
}

async function loadRecentSessions() {
    try {
        const res = await fetch(`${API_BASE}/api/db/recent`);
        const sessions = await res.json();
        const results = $('dbResults');
        if (!results) return;

        if (sessions.length === 0) {
            results.innerHTML = `
                <div style="opacity:0.8;text-align:center;padding:40px;background:rgba(255,255,255,0.03);border-radius:16px;border:1px dashed var(--glass-border);">
                    <div style="font-size:32px;margin-bottom:12px;">📭</div>
                    <div style="font-weight:600;color:var(--text-primary);">No Sessions Found</div>
                    <p style="font-size:12px;color:var(--text-secondary);margin-top:8px;">Start by adding a student in the <b>Student Panel</b> tab to begin tracking history.</p>
                </div>
            `;
            return;
        }

        results.innerHTML = `
            <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--therapeutic-teal);margin-bottom:15px;padding-left:10px;font-weight:700;">Recent Activity (Last 20)</div>
            ${sessions.map(s => `
                <div class="db-result-card">
                    <div>
                        <div style="font-weight:600;font-size:16px;">${s.student_name}</div>
                        <div style="font-size:12px;color:var(--text-secondary);">${s.class_name} — ${s.college_name}</div>
                        <div style="font-size:10px;color:var(--therapeutic-teal);margin-top:4px;font-family:'JetBrains Mono';">
                           Last Score: <b>${s.avg_focus}%</b> | ${Math.floor(s.duration / 60)}m ${s.duration % 60}s
                        </div>
                    </div>
                    <div style="display:flex;gap:12px;">
                         <button onclick="downloadReport('${s.student_id}', '${s.student_name}', '', '', '${s.class_name}', '${s.college_name}')" class="btn-db-action">📄 Report</button>
                         <button onclick="openModalForStudent('${s.student_id}', '${s.student_name}', '${s.class_name}', '${s.college_name}')" class="btn-db-action active">▶ Re-run</button>
                         <button onclick="deleteSession('${s.id}','${(s.student_name || '').replace(/'/g, '')}')" class="btn-db-action" style="background:rgba(239,68,68,0.2);color:#EF4444;">🗑️</button>
                    </div>
                </div>
            `).join('')}
        `;
    } catch (e) {
        console.error("Load recent sessions error", e);
    }
}

function downloadReport(id, name, roll, age, cls, clg) {
    const url = `${API_BASE}/api/report/${encodeURIComponent(id)}?name=${encodeURIComponent(name || '')}&roll_no=${encodeURIComponent(roll || '')}&age=${encodeURIComponent(age || '')}&class_name=${encodeURIComponent(cls || '')}&college_name=${encodeURIComponent(clg || '')}`;
    window.open(url, '_blank');
}

function openModalForStudent(id, name, cls, clg) {
    state.activeStudent = { id, name, cls, clg };
    $('modalStudentName').textContent = name;
    $('modalStudentMeta').textContent = `${cls || ''} — ${clg || ''}`;
    $('sessionModal').style.display = 'flex';
}

function closeModal() {
    $('sessionModal').style.display = 'none';
}

async function startSessionWithStudent() {
    closeModal();
    document.querySelector('.tab-btn[data-tab="monitor"]').click();
    // Guard against null activeStudent
    if (!state.activeStudent) {
        _startSessionInternal();
        return;
    }

    // Reset baseline for this specific student — fresh IAF + calibration
    try {
        await fetch(`${API_BASE}/api/session/start`, { method: 'POST' });
        showAlert(`Calibrating for ${state.activeStudent.name}... Sit still for 15 seconds.`, 'info', 6000);
    } catch (e) {
        console.error('Failed to reset baseline:', e);
    }

    _startSessionInternal();
    showActiveStudentUI(state.activeStudent.name);
}

function showActiveStudentUI(name) {
    const h = document.querySelector('.session-info');
    if (h) {
        h.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:10px;height:10px;border-radius:50%;background:#EF4444;animation:pulse-red 1s infinite;"></div>
                <div>
                   <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,0.4);">Recording Session for</div>
                   <div style="font-size:16px;font-weight:600;color:white;">${name}</div>
                </div>
            </div>
        `;
    }
}

function hideActiveStudentUI() {
    const h = document.querySelector('.session-info');
    if (h) h.innerHTML = '';
}

async function checkDBStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/db/status`);
        const data = await res.json();
        const bar = $('dbStatusBar');
        if (bar) {
            if (data.connected) {
                bar.innerHTML = '🟢 Connected to Supabase Cloud';
                bar.style.background = 'rgba(45,212,191,0.15)';
                bar.style.color = '#2DD4BF';
            } else {
                bar.innerHTML = '🔴 Supabase Key missing in config.py';
                bar.style.background = 'rgba(239, 68, 68, 0.1)';
                bar.style.color = '#EF4444';
            }
        }
    } catch (e) { }
}

// Initial loads
document.addEventListener('DOMContentLoaded', () => {
    checkDBStatus();
    loadRecentSessions();
});

// Periodic status check
setInterval(checkDBStatus, 10000);

// Global Exposure
window.loadClassesForStudent = loadClassesForStudent;
window.dbSearch = dbSearch;
window.loadRecentSessions = loadRecentSessions;
window.openModalForStudent = openModalForStudent;
window.downloadReport = downloadReport;
window.startSession = startSession;
window.closeModal = closeModal;
window.createCollege = createCollege;
window.createClass = createClass;
window.createStudent = createStudent;
window.showSPPanel = showSPPanel;
window.loadClassesForStudent = loadClassesForStudent;

// ═══════════════════════════════════════════════════════════════
//  DELETE OPERATIONS
// ═══════════════════════════════════════════════════════════════
async function deleteCollege(id, name) {
    if (!confirm(`Delete college "${name}"? This will also delete ALL classes, students, and sessions under it.`)) return;
    const res = await fetch(`${API_BASE}/api/college/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
    });
    const d = await res.json();
    if (d.status === 'ok') { showAlert(`Deleted college: ${name}`, 'info', 3000); loadColleges(); }
    else showAlert('Delete failed', 'error', 3000);
}

async function deleteClass(id, name, collegeId) {
    if (!confirm(`Delete class "${name}"? This will also delete ALL students and sessions in it.`)) return;
    const res = await fetch(`${API_BASE}/api/class/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
    });
    const d = await res.json();
    if (d.status === 'ok') { showAlert(`Deleted class: ${name}`, 'info', 3000); if (collegeId) loadClasses(collegeId); }
    else showAlert('Delete failed', 'error', 3000);
}

async function deleteStudent(id, name, classId) {
    if (!confirm(`Delete student "${name}"? This will also delete ALL their sessions.`)) return;
    const res = await fetch(`${API_BASE}/api/student/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
    });
    const d = await res.json();
    if (d.status === 'ok') {
        showAlert(`Deleted student: ${name}`, 'info', 3000);
        if (classId) loadStudents(classId);
        else { dbSearch(); loadRecentSessions(); }
    } else showAlert('Delete failed', 'error', 3000);
}

async function deleteSession(id, studentName) {
    if (!confirm(`Delete this session for "${studentName}"?`)) return;
    const res = await fetch(`${API_BASE}/api/session/delete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
    });
    const d = await res.json();
    if (d.status === 'ok') { showAlert('Session deleted', 'info', 3000); loadRecentSessions(); }
    else showAlert('Delete failed', 'error', 3000);
}

window.deleteCollege = deleteCollege;
window.deleteClass = deleteClass;
window.deleteStudent = deleteStudent;
window.deleteSession = deleteSession;
