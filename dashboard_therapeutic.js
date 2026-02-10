// ==========================
// FLOWSTATE THERAPEUTIC UI
// Ultra-Smooth Animations (60fps+)
// ==========================

const CONFIG = { api: 'http://localhost:5001/api' };

// ==========================
// 3D NEURAL SPHERE (Biofeedback-Linked)
// ==========================
(function init3D() {
    const canvas = document.getElementById('neuralCanvas');
    if (!canvas || typeof THREE === 'undefined') return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);

    // Therapeutic particle system (calming colors)
    const particleCount = 2500;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    // Distribute in sphere
    const radius = 5;
    for (let i = 0; i < particleCount; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = radius * Math.cbrt(Math.random());

        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);

        // Therapeutic teal gradient
        const colorMix = Math.random();
        colors[i * 3] = 0.18 + colorMix * 0.25;     // R (teal-cyan)
        colors[i * 3 + 1] = 0.83 - colorMix * 0.15; // G
        colors[i * 3 + 2] = 0.77 + colorMix * 0.18; // B (soft blue)
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.035,
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending,
        sizeAttenuation: true
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    camera.position.z = 7;

    // Biofeedback state
    window.neuralState = {
        speed: 0.0005,
        pulse: 0,
        zoom: 1.0,
        colorShift: 0
    };

    function animate() {
        requestAnimationFrame(animate);

        const state = window.neuralState;

        // Ultra-smooth rotation
        particles.rotation.x += state.speed;
        particles.rotation.y += state.speed * 1.3;

        // Breathing pulse
        state.pulse += 0.015;
        const scale = state.zoom + Math.sin(state.pulse) * 0.02;
        particles.scale.set(scale, scale, scale);

        renderer.render(scene, camera);
    }

    animate();

    // Smooth resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
})();

// ==========================
// TAB NAVIGATION (Butter-Smooth)
// ==========================
const tabs = document.querySelectorAll('.tab-btn');
const panels = document.querySelectorAll('.tab-panel');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetPanel = tab.dataset.tab;

        // Remove active from all
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));

        // Add active to clicked
        tab.classList.add('active');
        document.querySelector(`[data-panel="${targetPanel}"]`).classList.add('active');

        // Haptic feedback (if supported)
        if ('vibrate' in navigator) {
            navigator.vibrate(10);
        }
    });
});

// ==========================
// BLUETOOTH SCANNING (Real)
// ==========================
const modal = document.getElementById('scanModal');
const deviceList = document.getElementById('deviceList');

// One-Click Connect Logic
document.getElementById('scanBtn').onclick = async () => {
    const btn = document.getElementById('scanBtn');
    // Simple visual feedback
    const icon = btn.querySelector('.material-icons-round') || btn;
    icon.style.animation = 'spin 1s infinite linear';

    try {
        // Attempt Auto-Connect (Backend handles Cache or First-Found)
        const res = await fetch(`${CONFIG.api}/connect`);
        const data = await res.json();

        if (data.status === 'initiated' || data.status === 'already_connected') {
            // Success path - The status loop will update the UI when connected
            // Show toast
            showToast("🔍 Searching for Muse...");
        } else {
            // Error path - open manual scan
            modal.classList.add('active');
            scanDevices();
        }
    } catch (e) {
        // Fallback to manual if API fail
        modal.classList.add('active');
        scanDevices();
    }

    // Stop spin after 2s (Status loop takes over)
    setTimeout(() => {
        icon.style.animation = 'none';
    }, 2000);
};

// Right-click or Long Press for Manual Menu (Optional, or just keep modal for error)
// For now, we stick to One-Click priority.

function closeModal() {
    modal.classList.remove('active');
}

async function scanDevices() {
    deviceList.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div style="width: 40px; height: 40px; border: 3px solid var(--therapeutic-teal); border-top-color: transparent; border-radius: 50%; margin: 0 auto 16px; animation: spin 1s linear infinite;"></div>
            <div style="color: var(--text-secondary);">Scanning for Muse devices...</div>
        </div>
    `;

    try {
        const res = await fetch(`${CONFIG.api}/bluetooth/scan`); // Still keep this for manual if needed
        const data = await res.json();
        renderDevices(data.devices || []);
    } catch (e) {
        deviceList.innerHTML = `
            <div class="metric-card" style="text-align: center;">
                <div style="color: var(--warm-sand); margin-bottom: 12px; font-size: 32px;">⚠️</div>
                <div style="color: var(--text-secondary);">
                    Backend server not reachable.<br>
                    <small>Start the Python backend first.</small>
                </div>
            </div>
        `;
    }
}

function renderDevices(devices) {
    if (devices.length === 0) {
        deviceList.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
                No Muse devices found.<br>
                <small>Make sure your device is powered on.</small>
            </div>
        `;
        return;
    }

    deviceList.innerHTML = devices.map(d => `
        <div class="device-item" onclick="connectDevice('${d.address}')">
            <div class="device-name">${d.name || 'Unknown Device'}</div>
            <div class="device-address">${d.address}</div>
        </div>
    `).join('');
}

async function connectDevice(address) {
    deviceList.innerHTML = `<div style="text-align: center; padding: 40px 20px; color: var(--therapeutic-teal);">Connecting...</div>`;

    try {
        const res = await fetch(`${CONFIG.api}/bluetooth/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address })
        });
        const data = await res.json();

        if (data.success) {
            closeModal();
            updateData(); // Immediate refresh
        } else {
            deviceList.innerHTML = `<div style="text-align: center; padding: 40px 20px; color: var(--warm-sand);">Connection failed. Try again.</div>`;
        }
    } catch (e) {
        deviceList.innerHTML = `<div style="text-align: center; padding: 40px 20px; color: var(--warm-sand);">API Error</div>`;
    }
}

// ==========================
// SESSION RECORDING
// ==========================
let isRecording = false;

window.startSession = async function () {
    const btn = document.querySelector('.btn-primary');

    if (!isRecording) {
        try {
            const res = await fetch(`${CONFIG.api}/session/start`);
            const data = await res.json();
            if (data.ok) {
                isRecording = true;
                btn.innerHTML = '⏹ Stop';
                btn.style.background = 'linear-gradient(135deg, #EF4444, #DC2626)';
            }
        } catch (e) {
            console.warn('Failed to start recording');
        }
    } else {
        try {
            const res = await fetch(`${CONFIG.api}/session/stop`);
            const data = await res.json();
            if (data.ok) {
                isRecording = false;
                btn.innerHTML = '▶ Start';
                btn.style.background = 'linear-gradient(135deg, var(--therapeutic-teal), var(--calm-sky))';
            }
        } catch (e) {
            console.warn('Failed to stop recording');
        }
    }
};

// ==========================
// BREATH PACER (Biofeedback-Driven)
// ==========================
let pacerState = { phase: 0, speed: 0.05 };

window.toggleBreathPacer = (checked) => {
    const el = document.getElementById('breathPacerOverlay');
    if (checked) {
        el.classList.remove('hidden');
        requestAnimationFrame(biofeedbackLoop);
    } else {
        el.classList.add('hidden');
    }
};

window.toggleAICoach = (checked) => {
    // Check if API Key exists
    const key = document.getElementById('apiKeyInput').value;
    if (checked && !key) {
        showToast("⚠️ API Key Required in Settings");
        document.getElementById('aiToggle').checked = false;
        // Optionally switch to Settings tab
        setTimeout(() => {
            document.querySelector('[data-tab="settings"]').click();
        }, 1000);
        return;
    }

    if (checked) {
        showToast("🤖 AI Coach Active");
        // Start polling for insights
        window.aiInterval = setInterval(fetchInsights, 10000);
    } else {
        showToast("🤖 AI Coach Paused");
        clearInterval(window.aiInterval);
    }
};

async function fetchInsights() {
    // Placeholder for deeper integration
}

function biofeedbackLoop() {
    const el = document.getElementById('breathPacerOverlay');
    if (el.classList.contains('hidden')) return;

    const circle = document.getElementById('breathCircle');
    const text = document.getElementById('breathText');

    pacerState.phase += pacerState.speed;
    const val = (Math.sin(pacerState.phase) + 1) / 2; // 0 to 1

    const scale = 0.7 + (val * 0.8); // 0.7 to 1.5
    circle.style.transform = `scale(${scale})`;

    if (val > 0.9) text.innerHTML = `HOLD<br><span style="font-size:14px; opacity:0.8">♥️ ${window.currentBPM || '--'}</span>`;
    else if (Math.cos(pacerState.phase) > 0) text.innerHTML = `INHALE<br><span style="font-size:14px; opacity:0.8">♥️ ${window.currentBPM || '--'}</span>`;
    else text.innerHTML = `EXHALE<br><span style="font-size:14px; opacity:0.8">♥️ ${window.currentBPM || '--'}</span>`;

    requestAnimationFrame(biofeedbackLoop);
}

// ==========================
// CHARTS (Smooth Updates)
// ==========================
const ctxF = document.getElementById('focusChart').getContext('2d');
const focusChart = new Chart(ctxF, {
    type: 'line',
    data: {
        labels: Array(60).fill(''),
        datasets: [
            {
                label: 'Delta δ', // Reference Style
                data: Array(60).fill(0),
                borderColor: '#2DD4BF', // Cyan/Teal (Reference)
                backgroundColor: 'rgba(45, 212, 191, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: false
            },
            {
                label: 'Theta θ',
                data: Array(60).fill(0),
                borderColor: '#3B82F6', // Blue (Reference)
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: false
            },
            {
                label: 'Alpha α',
                data: Array(60).fill(0),
                borderColor: '#A855F7', // Purple (Reference)
                backgroundColor: 'rgba(168, 85, 247, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: false
            },
            {
                label: 'Beta β',
                data: Array(60).fill(0),
                borderColor: '#EC4899', // Pink (High Freq)
                backgroundColor: 'rgba(236, 72, 153, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: false
            },
            {
                label: 'Gamma γ',
                data: Array(60).fill(0),
                borderColor: '#F59E0B', // Orange (Peak Focus)
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                fill: false
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false, // DISABLED to stop Flickering
        interaction: {
            mode: 'nearest',
            intersect: false
        },
        scales: {
            x: {
                display: true,
                grid: { color: 'rgba(255, 255, 255, 0.05)', drawTicks: false },
                ticks: { display: false }
            },
            y: {
                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                min: 0,
                // Auto-scale
                ticks: { color: '#94A3B8', font: { size: 10 } }
            }
        },
        plugins: {
            legend: {
                position: 'top',
                align: 'end',
                labels: { boxWidth: 10, color: '#94A3B8', font: { size: 10 }, usePointStyle: true }
            }
        }
    }
});

const ctxS = document.getElementById('spectrumChart').getContext('2d');
const gradientS = ctxS.createLinearGradient(0, 0, 0, 200);
gradientS.addColorStop(0, 'rgba(45, 212, 191, 0.6)');
gradientS.addColorStop(1, 'rgba(45, 212, 191, 0)');

const spectrumChart = new Chart(ctxS, {
    type: 'line',
    data: {
        labels: ['Delta', 'Theta', 'Alpha', 'Beta', 'Gamma'],
        datasets: [{
            label: 'Power (uV²)',
            data: [10, 20, 50, 20, 10],
            backgroundColor: gradientS,
            borderColor: '#2DD4BF',
            borderWidth: 3,
            fill: true,
            tension: 0.5,
            pointRadius: 5,
            pointBackgroundColor: '#2DD4BF',
            pointBorderColor: '#1E3A5F',
            pointBorderWidth: 2
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 400, easing: 'easeOutQuart' },
        scales: {
            x: { grid: { display: false }, ticks: { color: '#94A3B8', font: { size: 11 } } },
            y: { display: false }
        },
        plugins: { legend: { display: false } }
    }
});

// GYRO CHART
const ctxG = document.getElementById('gyroChart').getContext('2d');
const gyroChart = new Chart(ctxG, {
    type: 'line',
    data: {
        labels: Array(60).fill(''),
        datasets: [
            {
                label: 'Pitch',
                data: Array(60).fill(0),
                borderColor: '#F472B6', // Pink
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.4
            },
            {
                label: 'Roll',
                data: Array(60).fill(0),
                borderColor: '#FACC15', // Yellow
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.4
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false, // Performance
        scales: {
            x: { display: false },
            y: {
                min: -180, max: 180,
                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                ticks: { color: '#94A3B8' }
            }
        },
        plugins: { legend: { display: true, labels: { color: '#94A3B8' } } }
    }
});

// HISTORY CHART (Analytics)
let historyChart;
function initHistoryChart() {
    const ctxH = document.getElementById('historyChart').getContext('2d');
    historyChart = new Chart(ctxH, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Avg Focus Score',
                data: [],
                backgroundColor: '#2DD4BF',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#94A3B8' } },
                x: { grid: { display: false }, ticks: { color: '#94A3B8' } }
            },
            plugins: { legend: { display: false } }
        }
    });
}
// Init immediately
if (document.getElementById('historyChart')) initHistoryChart();


// ==========================
// REAL-TIME DATA UPDATES
// ==========================
async function updateData() {
    try {
        // --- 1D KALMAN FILTER CLASS ---
        class KalmanFilter {
            constructor(R = 1, Q = 1, A = 1, B = 0, C = 1) {
                this.R = R; // Noise covariance (Measurement Noise)
                this.Q = Q; // Process covariance (Actual Value Noise)
                this.A = A; // State vector
                this.B = B; // Control vector
                this.C = C; // Measurement vector
                this.cov = NaN;
                this.x = NaN; // Estimated signal
            }

            filter(measurement) {
                if (isNaN(this.x)) {
                    this.x = measurement;
                    this.cov = this.R;
                    return measurement;
                }

                // Prediction
                const predX = (this.A * this.x) + (this.B * 0);
                const predCov = ((this.A * this.cov) * this.A) + this.Q;

                // Correction
                const K = predCov * this.C * (1 / ((this.C * predCov * this.C) + this.R));
                this.x = predX + K * (measurement - (this.C * predX));
                this.cov = predCov - (K * this.C * predCov);

                return this.x;
            }
        }

        // Initialize Filters (Global Scope via window for persistence)
        if (!window.filters) {
            window.filters = {
                focus: new KalmanFilter(0.01, 1),   // R=0.01 (Raw/Instant), Q=1 (Fast moves)
                bpm: new KalmanFilter(0.1, 1),      // Cleaner signal but reactive
                fatigue: new KalmanFilter(0.1, 0.1), // Faster update
                valence: new KalmanFilter(0.1, 0.5) // Reactive
            };
        }

        // Fetch with 5s Timeout (More tolerant)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        // [MODIFIED] Fetch from RAW DATA endpoint for full fidelity
        const res = await fetch(`${CONFIG.api}/raw_data`, { signal: controller.signal });
        clearTimeout(timeoutId);

        const data = await res.json();

        // Map raw_data structure to legacy structure for compatibility if needed
        // The backend /api/raw_data returns a flattened structure with 'focus_score' etc.
        // We'll normalize it here for the rest of the UI.
        const normalized = {
            connected: data.connected,
            signal_ok: data.connected,
            focus: data.focus_score,
            bpm: data.heart_rate,
            hrv: data.hrv_rmssd,
            fatigue: 0, // Not yet in raw_data, default 0
            valence: 0, // Not yet in raw_data, default 0
            bands: data.bands,
            posture_values: {  // Derive pitch/roll from accelerometer?
                pitch: Math.atan2(data.accelerometer.y, data.accelerometer.z) * 180 / Math.PI,
                roll: Math.atan2(-data.accelerometer.x, Math.sqrt(data.accelerometer.y ** 2 + data.accelerometer.z ** 2)) * 180 / Math.PI
            },
            // Pass through raw for debug
            raw: data
        };

        // Re-assign data to normalized for consistent UI usage downstream
        // But keep 'data' available if we need specific raw fields
        const uiData = normalized;


        // --- ZOMBIE SIGNAL CHECK ---
        const checkZombieSignal = (d) => {
            if (d.connected) {
                hideZombieAlert();
            } else {
                hideZombieAlert();
                const statusEl = document.getElementById('deviceStatus');
                if (statusEl) statusEl.innerText = "AUTO-REPAIR...";
            }
        };

        const showZombieAlert = () => {
            // ... existing alert logic ...
        };

        const hideZombieAlert = () => {
            const alert = document.getElementById('zombieAlert');
            if (alert) alert.remove();
        };

        // --- SENIOR DEV DEBUGGER ---
        const debugEl = document.getElementById('debugOverlay');
        const updateDebug = (msg) => {
            if (debugEl) {
                debugEl.innerHTML = `
                    <div style="font-size:10px; font-family:monospace; background:rgba(0,0,0,0.8); padding:5px; position:fixed; bottom:0; right:0; z-index:9999; color:#0f0;">
                        API: RAW_DATA OK<br>
                        CONN: ${uiData.connected}<br>
                        FOCUS: ${uiData.focus?.toFixed(1)}<br>
                        ALPHA: ${uiData.bands?.alpha?.toFixed(1)}<br>
                        STATUS: ${msg}
                    </div>
                `;
            }
        };

        checkZombieSignal(uiData);

        // ---------------------------

        try {
            updateDebug("Updating DOM...");

            // Metrics

            // 1. FOCUS (Kalman Smoothed)
            const rawFocus = uiData.focus || 0;
            const smoothFocus = window.filters.focus.filter(rawFocus);
            const fVal = Math.round(smoothFocus);

            const fEl = document.getElementById('focusValue');
            if (fEl) fEl.innerHTML = `${fVal}<span class="card-unit">%</span>`;

            // 1.1 ARTIFACTS (Blink / Jaw) - Overrides Fatigue Display
            const blinkEl = document.getElementById('blinkValue');
            if (blinkEl) {
                // Check raw flags from backend
                if (uiData.raw && uiData.raw.jaw_clench) {
                    blinkEl.innerHTML = `JAW!<span class="card-unit">⚠️</span>`;
                    blinkEl.style.color = '#F87171'; // Red
                    // Optional: Visual shake effect could go here
                } else if (uiData.raw && uiData.raw.blink) {
                    blinkEl.innerHTML = `BLINK<span class="card-unit">👁️</span>`;
                    blinkEl.style.color = '#60A5FA'; // Blue
                } else {
                    // Default Fatigue
                    const rawFatigue = (uiData.fatigue || 0) * 100;
                    // const smoothFatigue = window.filters.fatigue.filter(rawFatigue); 
                    // Use 0 for now as fatigue calculator isn't active
                    blinkEl.innerHTML = `0<span class="card-unit">%</span>`;
                    blinkEl.style.color = 'white';
                }
            }

            // 2. BPM (Kalman Smoothed)
            const rawBpm = uiData.bpm || 0;
            // Only filter if valid pulse
            let smoothBpm = 0;
            if (rawBpm > 30) {
                smoothBpm = window.filters.bpm.filter(rawBpm);
            } else {
                window.filters.bpm.x = NaN; // Reset filter if pulse lost
            }

            const bpmEl = document.getElementById('bpmValue');
            if (bpmEl) {
                if (smoothBpm > 30) {
                    bpmEl.innerHTML = `${Math.round(smoothBpm)}<span class="card-unit">BPM</span>`;
                    bpmEl.style.fontSize = "42px";
                } else {
                    bpmEl.innerHTML = `No Pulse`;
                    bpmEl.style.fontSize = "24px";
                }
            }

            if (uiData.hrv) {
                const hEl = document.getElementById('hrvValue');
                if (hEl) hEl.innerText = Math.round(uiData.hrv);
            }

            // 3. FATIGUE (Placeholder)
            const fatigueEl = document.getElementById('blinkValue');
            if (fatigueEl) {
                // blinkEl.innerHTML = `--<span class="card-unit">%</span>`;
                // Logic moved to "1.1 ARTIFACTS" to override this.
                // Leaving empty to avoid overwriting valid blink data.
            }

            // 4. MOOD / VALENCE (Placeholder)
            const valEl = document.getElementById('valenceValue');
            const valLabel = document.getElementById('valenceLabel');
            if (valEl) {
                valEl.innerText = "--";
                valLabel.innerText = "Calibrating";
                valLabel.style.color = "#a0aec0";
            }

            // Connection status
            const connEl = document.getElementById('connectionStatus');
            const badge = document.getElementById('neuroStateBadge');

            if (connEl) {
                if (uiData.connected) {
                    connEl.innerText = "ONLINE";
                    connEl.className = "status-text online";
                } else {
                    connEl.innerText = "OFFLINE";
                    connEl.className = "status-text offline";
                }
            }

            // Charts (ALWAYS UPDATE - SHOW RAW NOISE)
            // If bands missing, push 0 to keep chart moving
            const delta = uiData.bands ? (uiData.bands.delta || 0) : 0;
            const theta = uiData.bands ? (uiData.bands.theta || 0) : 0;
            const alpha = uiData.bands ? (uiData.bands.alpha || 0) : 0;
            const beta = uiData.bands ? (uiData.bands.beta || 0) : 0;
            const gamma = uiData.bands ? (uiData.bands.gamma || 0) : 0;

            if (typeof focusChart !== 'undefined') {
                // Shift all
                focusChart.data.datasets.forEach(ds => ds.data.shift());

                // Push new (Order: Delta, Theta, Alpha, Beta, Gamma)
                focusChart.data.datasets[0].data.push(delta);
                focusChart.data.datasets[1].data.push(theta);
                focusChart.data.datasets[2].data.push(alpha);
                focusChart.data.datasets[3].data.push(beta);
                focusChart.data.datasets[4].data.push(gamma);

                focusChart.update('none'); // No animation mode
            }

            if (typeof spectrumChart !== 'undefined') {
                spectrumChart.data.datasets[0].data = [
                    uiData.bands ? (uiData.bands.delta || 0) : 0,
                    uiData.bands ? (uiData.bands.theta || 0) : 0,
                    uiData.bands ? (uiData.bands.alpha || 0) : 0,
                    uiData.bands ? (uiData.bands.beta || 0) : 0,
                    uiData.bands ? (uiData.bands.gamma || 0) : 0
                ];
                spectrumChart.update('none');
            }

            // Gyro Chart
            const pitch = uiData.posture_values ? (uiData.posture_values.pitch || 0) : 0;
            const roll = uiData.posture_values ? (uiData.posture_values.roll || 0) : 0;

            if (typeof gyroChart !== 'undefined') {
                gyroChart.data.datasets[0].data.push(pitch);
                gyroChart.data.datasets[0].data.shift();
                gyroChart.data.datasets[1].data.push(roll);
                gyroChart.data.datasets[1].data.shift();
                gyroChart.update('none');
            }

            updateDebug("SUCCESS: Rendered");

        } catch (e) {
            updateDebug(`CRASH: ${e.message}`);
            console.error(e);
        }

        // AUDIO BIOFEEDBACK
        if (typeof audioCoach !== 'undefined' && data.bands && window.audioEnabled) {
            audioCoach.update(data.focus || 0);
        }
        // 3D Sphere Biofeedback
        if (window.neuralState && data.bands) {
            const alpha = data.bands.alpha || 0.5;
            const beta = data.bands.beta || 0.5;

            // Calm (high alpha) = slow, Stressed (high beta) = fast
            const targetSpeed = 0.0003 + (beta * 0.002) - (alpha * 0.001);
            window.neuralState.speed += (targetSpeed - window.neuralState.speed) * 0.03;

            // Zoom based on focus
            const targetZoom = 0.92 + (data.focus * 0.18);
            window.neuralState.zoom += (targetZoom - window.neuralState.zoom) * 0.015;

            // ============================
            // THE MIRROR TEST (Artifact Flare)
            // ============================
            if (data.artifact_event) {
                const canvas = document.getElementById('neuralCanvas');
                if (data.artifact_event === 'JAW_CLENCH') {
                    // RED FLASH
                    canvas.style.filter = 'drop-shadow(0 0 30px #ff2a2a) brightness(2.0)';
                    window.neuralState.colorShift = 1.0;
                    showToast("😬 Jaw Clench Detected");
                    setTimeout(() => { canvas.style.filter = ''; window.neuralState.colorShift = 0; }, 200);
                } else if (data.artifact_event === 'BLINK') {
                    // WHITE FLASH
                    canvas.style.filter = 'brightness(1.5)';
                    setTimeout(() => { canvas.style.filter = ''; }, 100);
                }
            }
        }

        // RESOANCE PACER TUNING
        // Goal: Guide user to 0.1Hz (6 breaths/min) but slow down if stressed
        if (data.bpm && data.bpm > 0) {
            window.currentBPM = Math.round(data.bpm);

            // If Heart Rate is high (>80), force SLOW breathing (Parasympathetic activation)
            // If Heart Rate is ideal (60-70), maintain Coherence Rhythm (6bpm)
            let targetSpeed = 0.045; // Default ~6bpm

            if (data.bpm > 85 || (data.hrv && data.hrv < 30)) {
                targetSpeed = 0.030; // Slow down to ~4bpm (Deep Calm)
            } else if (data.bpm < 60) {
                targetSpeed = 0.050; // Normal rhythm
            }

            // Smooth transition
            pacerState.speed += (targetSpeed - pacerState.speed) * 0.05;
        } else {
            window.currentBPM = '--';
        }

    } catch (e) {
        // Handle Disconnect (Kill Audio)
        if (typeof audioCoach !== 'undefined' && audioCoach.isPlaying) {
            audioCoach.stop();
        }

        // Show Offline Status with Error Detail
        const connEl = document.getElementById('connectionStatus');
        if (connEl) {
            connEl.innerText = `ERROR: ${e.name}`; // e.g. "TypeError" or "AbortError"
            connEl.className = "status-text offline";

            // Log full error to debug overlay if exists
            const debugEl = document.getElementById('debugOverlay');
            if (debugEl) debugEl.innerHTML = `<div style="background:red; color:white; padding:5px;">FETCH FAILED: ${e.message}</div>`;
        }
    }
}

// RECURSIVE POLLING (Prevents Pile-up & Flickering)
// Only fetch next packet AFTER previous one finishes.
async function dataLoop() {
    await updateData();
    setTimeout(dataLoop, 500); // Wait 500ms *after* finish
}
dataLoop(); // Start Loop

// Battery polling
setInterval(async () => {
    try {
        const res = await fetch(`${CONFIG.api}/bluetooth/battery`);
        const data = await res.json();
        if (data.battery !== null && data.battery >= 0) {
            document.getElementById('batteryLevel').innerText = `${data.battery}%`;
        }
    } catch (e) { }
}, 60000);

// ==========================
// AI COACH TOGGLE (Real)
// ==========================
window.toggleAICoach = async (checked) => {
    try {
        const res = await fetch(`${CONFIG.api}/coach/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: checked })
        });
        const data = await res.json();
        console.log('AI Coach:', data.enabled ? 'Active' : 'Silent');

        if (data.enabled) {
            startGuidanceLoop();
        }
    } catch (e) {
        console.warn("AI Coach API error");
    }
};

let guidanceInterval;
function startGuidanceLoop() {
    if (guidanceInterval) clearInterval(guidanceInterval);

    guidanceInterval = setInterval(async () => {
        const toggle = document.getElementById('aiToggle');
        if (!toggle.checked) {
            clearInterval(guidanceInterval);
            return;
        }

        try {
            const res = await fetch(`${CONFIG.api}/coach/guidance`);
            const data = await res.json();
            if (data.guidance) {
                // Show floating guidance toast or update UI
                showToast(data.guidance);
            }
        } catch (e) { }
    }, 10000); // Check every 10 seconds
}

function showToast(message) {
    // Create or reuse toast element
    let toast = document.getElementById('aiToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'aiToast';
        toast.style.cssText = `
            position: fixed; top: 100px; right: 32px;
            background: rgba(10, 46, 77, 0.9);
            border: 1px solid var(--therapeutic-teal);
            padding: 16px 24px;
            border-radius: 12px;
            color: var(--therapeutic-teal);
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            max-width: 300px;
        `;
        document.body.appendChild(toast);
    }

    toast.innerHTML = `<strong>🤖 AI Guide:</strong><br>${message}`;
    toast.style.transform = 'translateX(0)';

    // Auto hide after 8s
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
    }, 8000);
}

// Load Insights when tab clicked
document.querySelector('[data-tab="insights"]').addEventListener('click', async () => {
    const container = document.querySelector('[data-panel="insights"] .metric-card p');
    container.innerHTML = 'Generating insight report... <span style="display:inline-block; animation:spin 1s infinite">⏳</span>';

    try {
        const res = await fetch(`${CONFIG.api}/session/report`);
        const data = await res.json();
        container.innerHTML = data.report.replace(/\n/g, '<br>');
    } catch (e) {
        container.innerHTML = 'Unable to generate report. Start a session first.';
    }
});

// ==========================
// SPIN ANIMATION (for loading)
// ==========================
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// ==========================
// ANALYTICS & SETTINGS
// ==========================

async function fetchHistory() {
    try {
        const res = await fetch(`${CONFIG.api}/history`);
        const data = await res.json();
        const history = data.history || [];

        if (typeof historyChart !== 'undefined' && historyChart) {
            historyChart.data.labels = history.map(s => {
                const date = new Date(s.date);
                return `${date.getMonth() + 1}/${date.getDate()}`;
            });
            historyChart.data.datasets[0].data = history.map(s => s.avg_focus);
            historyChart.update();
        }

        const totalMins = Math.round(history.reduce((sum, s) => sum + s.duration, 0));
        const minVal = document.getElementById('totalMinutesVal');
        const sessVal = document.getElementById('totalSessionsVal');
        if (minVal) minVal.innerText = totalMins + "m";
        if (sessVal) sessVal.innerText = history.length;

    } catch (e) {
        console.error("History fetch failed:", e);
    }
}

async function initSettings() {
    try {
        const res = await fetch(`${CONFIG.api}/settings`);
        const cfg = await res.json();

        const notchSelect = document.getElementById('notchSelect');
        const volSlider = document.getElementById('audioVolume');

        if (notchSelect) notchSelect.value = cfg.notch_freq || 50;
        if (volSlider) volSlider.value = cfg.audio_volume || 50;

    } catch (e) { }

    document.getElementById('notchFilter')?.addEventListener('change', async (e) => {
        await fetch(`${CONFIG.api}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notch_freq: parseInt(e.target.value) })
        });
        showToast("Notch Filter Updated");
    });

    document.getElementById('audioVolume')?.addEventListener('input', async (e) => {
        await fetch(`${CONFIG.api}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio_volume: parseInt(e.target.value) })
        });
    });
}

// Bind Tabs if they exist
const analyticsTab = document.querySelector('[data-tab="analytics"]');
if (analyticsTab) {
    analyticsTab.addEventListener('click', () => {
        if (typeof initHistoryChart === 'function' && !historyChart) initHistoryChart();
        fetchHistory();
    });
}

const settingsTab = document.querySelector('[data-tab="settings"]');
if (settingsTab) {
    settingsTab.addEventListener('click', () => {
        initSettings();
    });
}

// ==========================
// AUDIO FEEDBACK ENGINE (Procedural Storm)
// ==========================
class SoundEngine {
    constructor() {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        this.masterGain = this.ctx.createGain();
        this.masterGain.connect(this.ctx.destination);
        this.masterGain.gain.value = 0;
        this.isPlaying = false;

        // Binaural Oscillators (Singing Bowl Effect)
        this.osc1 = null;
        this.osc2 = null;
    }

    start() {
        if (this.ctx.state === 'suspended') this.ctx.resume();
        if (this.isPlaying) return;

        // Base 200Hz + Focus Frequency (Gamma 40Hz target)
        this.osc1 = this.ctx.createOscillator();
        this.osc1.type = 'sine';
        this.osc1.frequency.value = 200;

        this.osc2 = this.ctx.createOscillator();
        this.osc2.type = 'sine';
        this.osc2.frequency.value = 240; // 40Hz beat diff

        this.osc1.connect(this.masterGain);
        this.osc2.connect(this.masterGain);

        this.osc1.start();
        this.osc2.start();

        // Fade in
        this.masterGain.gain.setTargetAtTime(0.3, this.ctx.currentTime, 2);
        this.isPlaying = true;
    }

    stop() {
        if (!this.isPlaying) return;
        this.masterGain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.5);
        setTimeout(() => {
            if (this.osc1) this.osc1.stop();
            if (this.osc2) this.osc2.stop();
            this.isPlaying = false;
        }, 600);
    }

    update(focusScore) {
        if (!this.isPlaying) return;

        // TEACHING MODE:
        // Reward High Focus with Clear, Louder Sound (Positive Reinforcement)
        // Punish Low Focus with Silence (Extinction)

        // Target: Focus > 0.5 starts sound. Peak at 1.0.
        const vol = Math.max(0, (focusScore - 0.3) * 0.8);
        this.masterGain.gain.setTargetAtTime(vol, this.ctx.currentTime, 0.5);

        // Modulate pitch slightly for feedback
        // Higher Focus = Higher Vibration (Gamma)
        if (this.osc2) {
            const beat = 10 + (focusScore * 30);
            this.osc2.frequency.setTargetAtTime(200 + beat, this.ctx.currentTime, 0.5);
        }
    }
}

// Global Instance
const audioCoach = new SoundEngine();

// ==========================
// TAB LOGIC
// ==========================
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const panel = document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`);
        if (panel) panel.classList.add('active');

        if (btn.dataset.tab === 'analytics') fetchHistory();
        if (btn.dataset.tab === 'settings') loadSettings();
    });
});

// ==========================
// HISTORY / ANALYTICS
// ==========================
async function fetchHistory() {
    try {
        const res = await fetch(`${CONFIG.api}/history`);
        const data = await res.json();
        const history = data.history || [];

        if (typeof historyChart !== 'undefined' && historyChart) {
            historyChart.data.labels = history.map(s => {
                const date = new Date(s.date);
                return `${date.getMonth() + 1}/${date.getDate()}`;
            });
            historyChart.data.datasets[0].data = history.map(s => s.avg_focus);
            historyChart.update();
        }

        const totalMins = Math.round(history.reduce((sum, s) => sum + s.duration, 0));
        const minVal = document.getElementById('totalSessions');
        if (minVal) minVal.innerText = history.length;

        const avgF = history.length > 0 ? (history.reduce((sum, s) => sum + s.avg_focus, 0) / history.length) : 0;
        const avgVal = document.getElementById('avgFocus');
        if (avgVal) avgVal.innerHTML = Math.round(avgF) + '<span class="card-unit">%</span>';

    } catch (e) { console.error("History error", e); }
}

// ==========================
// TOGGLES
// ==========================
window.toggleAICoach = (checked) => {
    const key = document.getElementById('apiKeyInput').value;
    if (checked && !key) {
        showToast("⚠️ API Key Required in Settings");
        document.getElementById('aiToggle').checked = false;
        setTimeout(() => document.querySelector('[data-tab="settings"]').click(), 1000);
        return;
    }
    if (checked) {
        showToast("🤖 AI Coach Active");
        window.aiInterval = setInterval(fetchInsights, 10000);
    } else {
        showToast("🤖 AI Coach Paused");
        clearInterval(window.aiInterval);
    }
};

window.audioEnabled = false;
window.toggleAudio = function (checked) {
    window.audioEnabled = checked;
    if (checked) {
        if (audioCoach.ctx.state === 'suspended') audioCoach.ctx.resume();
        audioCoach.start();
        showToast("🔊 Audio Enabled");
    } else {
        audioCoach.stop();
        showToast("🔇 Audio Muted");
    }
};

// AI coach removed

// ==========================
// SETTINGS
// ==========================
async function loadSettings() {
    try {
        const res = await fetch(`${CONFIG.api}/settings`);
        const cfg = await res.json();
        if (cfg.gemini_key) document.getElementById('apiKeyInput').value = cfg.gemini_key;
        if (cfg.notch_freq) document.getElementById('notchSelect').value = cfg.notch_freq;
    } catch (e) { }
}

window.saveSettings = async function () {
    try {
        await fetch(`${CONFIG.api}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notch_freq: notch })
        });
        showToast("✅ Settings Saved");
    } catch (e) { showToast("⚠️ Save Failed"); }
};

// ==========================
// CALIBRATION LOGIC
// ==========================
window.startCalibration = async function () {
    try {
        await fetch(`${CONFIG.api}/calibrate/start`, { method: 'POST' });
        document.getElementById('calibrationOverlay').style.display = 'flex';
        document.getElementById('calibProgress').style.width = '0%';
        window.calibInterval = setInterval(pollCalibration, 1000);
    } catch (e) { showToast("⚠️ Connection Error"); }
};

window.pollCalibration = async function () {
    try {
        const res = await fetch(`${CONFIG.api}/calibrate/status`);
        const data = await res.json();
        const bar = document.getElementById('calibProgress');

        if (bar) bar.style.width = `${data.progress}%`;

        if (data.done) {
            clearInterval(window.calibInterval);
            document.getElementById('calibrationOverlay').style.display = 'none';
            showToast("✅ Brain Profile Learned!");
        }
    } catch (e) { }
};

window.cancelCalibration = async function () {
    await fetch(`${CONFIG.api}/calibrate/cancel`, { method: 'POST' });
    clearInterval(window.calibInterval);
    document.getElementById('calibrationOverlay').style.display = 'none';
};

// ==========================
// AI COACH LOGIC (Gemini)
// ==========================
// AI Logic Removed

// Init
loadSettings();
document.body.addEventListener('click', () => {
    if (audioCoach && audioCoach.ctx.state === 'suspended') audioCoach.ctx.resume();
}, { once: true });

// Wire up the Connect Button
document.getElementById('scanBtn')?.addEventListener('click', () => {
    connectSensor();
});

// Define Connect Function
async function connectSensor() {
    showToast("🔍 Scanning for Muse...", 3000);
    try {
        const res = await fetch(`${CONFIG.api}/connect`);
        const data = await res.json();
        if (data.status === 'initiated') {
            showToast("🚀 Initiating Bluetooth Link...", 5000);
        } else if (data.status === 'already_connected') {
            showToast("✅ Already Connected");
        } else {
            showToast("⚠️ Connection Error: " + data.message);
        }
    } catch (e) {
        showToast("❌ Server Error: " + e.message);
    }
}

// Wire up Disconnect Button
document.getElementById('disconnectBtn')?.addEventListener('click', async () => {
    try {
        await fetch(`${CONFIG.api}/disconnect`);
        showToast("🔌 Disconnecting...");
    } catch (e) { console.error(e); }
});

// UI State Manager for Connection
function updateConnectionUI(data) {
    const scanBtn = document.getElementById('scanBtn');
    const deviceStats = document.getElementById('deviceStats');
    const deviceName = document.getElementById('deviceName');
    const batteryLevel = document.getElementById('batteryLevel');
    const wearAlert = document.getElementById('wearMuseAlert');

    if (data.connected || data.status === 'getting_ready') { // weak check
        if (scanBtn) scanBtn.style.display = 'none';
        if (deviceStats) deviceStats.style.display = 'block';

        if (deviceName && data.device_name) deviceName.textContent = data.device_name;
        if (batteryLevel && data.battery_level) batteryLevel.textContent = data.battery_level + "%";

        // Wear Alert Logic
        if (wearAlert) {
            // signal_ok is true if good signal. false if artifact/bad. 
            // If connected but signal bad -> Wear Alert
            wearAlert.style.display = (data.connected && !data.signal_ok) ? 'block' : 'none';
        }
    } else {
        if (scanBtn) scanBtn.style.display = 'block';
        if (deviceStats) deviceStats.style.display = 'none';
    }
}

// START ENGINE
setInterval(updateData, 100); // 10Hz Update Loop

