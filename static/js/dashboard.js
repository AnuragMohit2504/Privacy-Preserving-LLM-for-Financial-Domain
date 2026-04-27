let triggeringRound = false;

let state = {
    uploadedFile: null,
    fileType: null,
    currentSection: 'dashboard',
    flStatus: { status: 'offline' },
    chatHistory: [],
    theme: 'dark',
    // Real per-round history tracked locally
    roundHistory: {
        rounds: [],
        accuracy: [],
        epsilon: []
    }
};

let chartsLoadedForFile = null;
let currentPeriod = "monthly";

const BACKEND_URL = window.location.origin;
const FL_UPDATE_INTERVAL = 10000;

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    initTheme();
    initNavigation();
    initFLMonitoring();
    initCharts();
    loadDashboardData();

    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('input', autoResizeTextarea);
    }
}

// ==================== THEME ====================

function initTheme() {
    const savedTheme = localStorage.getItem('fingpt-theme') || 'dark';
    state.theme = savedTheme;
    document.body.className = `${savedTheme}-theme`;
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.body.className = `${state.theme}-theme`;
    localStorage.setItem('fingpt-theme', state.theme);

    const icon = document.getElementById('theme-icon');
    if (icon) {
        if (state.theme === 'light') {
            icon.innerHTML = '<path d="M10 2C8.34315 2 7 3.34315 7 5C7 6.65685 8.34315 8 10 8C11.6569 8 13 6.65685 13 5C13 3.34315 11.6569 2 10 2Z" fill="currentColor"/><path d="M10 18C10 16.8954 9.10457 16 8 16H4C2.89543 16 2 16.8954 2 18V18" stroke="currentColor" stroke-width="1.5"/>';
        } else {
            icon.innerHTML = '<path d="M10 2V4M10 16V18M4 10H2M18 10H16M15.5 4.5L14 6M6 14L4.5 15.5M15.5 15.5L14 14M6 6L4.5 4.5M13 10C13 11.7 11.7 13 10 13C8.3 13 7 11.7 7 10C7 8.3 8.3 7 10 7C11.7 7 13 8.3 13 10Z" stroke="currentColor" stroke-width="1.5"/>';
        }
    }
    initCharts();
}

// ==================== NAVIGATION ====================

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            navigateToSection(section);
        });
    });
}

function navigateToSection(section) {
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    const navItem = document.querySelector(`[data-section="${section}"]`);
    if (navItem) navItem.classList.add('active');

    document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
    const targetSection = document.getElementById(`section-${section}`);
    if (targetSection) targetSection.classList.add('active');

    const titles = {
        'dashboard': 'Dashboard',
        'chat': 'AI Assistant',
        'analytics': 'Analytics',
        'fl-monitor': 'FL Monitor'
    };

    document.getElementById('page-title').textContent = titles[section] || 'Dashboard';
    document.getElementById('breadcrumb-current').textContent = titles[section] || 'Dashboard';

    state.currentSection = section;

    if (section === 'fl-monitor') {
        updateFLMonitor();
    } else if (section === 'analytics') {
        updateAnalyticsCharts();
    } else if (section === 'dashboard') {
        initCharts();
    }
}

// ==================== FL MONITORING ====================

async function initFLMonitoring() {
    await updateFLStatus();
    setInterval(updateFLStatus, FL_UPDATE_INTERVAL);
}

async function updateFLStatus() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/fl_status`);
        if (!response.ok) throw new Error("FL status API failed");
        const data = await response.json();
        state.flStatus = data;
        updateFLIndicators(data);
    } catch (error) {
        console.error('FL status check failed:', error);
        state.flStatus = { status: 'offline' };
        updateFLIndicators({ status: 'offline' });
    }
}

function updateFLIndicators(data) {
    const badge = document.getElementById('fl-status-badge');
    const indicator = document.getElementById('fl-status-indicator');
    if (!badge || !indicator) return;

    const statusMap = {
        'running': { class: '', text: 'Online', color: '#10b981' },
        'idle': { class: 'idle', text: 'Idle', color: '#f59e0b' },
        'offline': { class: 'offline', text: 'Offline', color: '#ef4444' }
    };

    const status = statusMap[data.status] || statusMap.offline;
    badge.style.color = status.color;
    indicator.className = `status-indicator ${status.class}`;
    indicator.querySelector('.status-text').textContent = status.text;

    if (data.stats) {
        const round = data.stats.current_round || 0;
        const clients = data.stats.active_clients || 0;
        const epsilon = data.stats.total_epsilon || 0;
        const accuracy = data.stats.accuracy || 0;

        updateElement('stat-fl-rounds', round);
        updateElement('stat-clients', clients);
        updateElement('stat-epsilon', epsilon.toFixed(2));
        updateElement('stat-transactions', data.stats.pending_features || 0);

        updateElement('fl-current-round', round);
        updateElement('fl-active-clients', clients);
        updateElement('fl-privacy-budget', epsilon.toFixed(2));
        updateElement('fl-accuracy', accuracy > 0 ? (accuracy * 100).toFixed(1) + '%' : '--');

        // Track real history for charts
        const lastRound = state.roundHistory.rounds.slice(-1)[0];
        if (round > 0 && round !== lastRound) {
            state.roundHistory.rounds.push(round);
            state.roundHistory.accuracy.push(parseFloat(accuracy.toFixed(3)));
            state.roundHistory.epsilon.push(parseFloat(epsilon.toFixed(2)));

            // Refresh FL charts if we're on that tab
            if (state.currentSection === 'fl-monitor') {
                updateFLCharts();
            }
        }
    }

    if (data.components) {
        updateComponentStatus(data.components);
    }
}

function updateComponentStatus(components) {
    const statusDiv = document.getElementById('component-status');
    if (!statusDiv) return;

    const componentNames = {
        'homomorphic_encryption': 'Homomorphic Encryption',
        'differential_privacy': 'Differential Privacy',
        'noise_mechanism': 'Noise Mechanism',
        'federated_aggregation': 'Federated Aggregation',
        'secure_aggregation': 'Secure Aggregation',
        'audit_logging': 'Audit Logging'
    };

    const icons = {
        'homomorphic_encryption': '🔐',
        'differential_privacy': '🛡️',
        'noise_mechanism': '🎲',
        'federated_aggregation': '🔒',
        'secure_aggregation': '🔒',
        'audit_logging': '📝'
    };

    // Special badge labels for planned/string values
    function getBadge(value) {
        if (value === true) return { label: 'Active', cls: 'active' };
        if (value === false) return { label: 'Inactive', cls: 'inactive' };
        if (value === 'planned') return { label: 'Planned', cls: 'planned' };
        if (value === 'laplace') return { label: 'Laplace DP', cls: 'active' };
        return { label: String(value), cls: 'inactive' };
    }

    statusDiv.innerHTML = '';
    Object.entries(components).forEach(([key, value]) => {
        const badge = getBadge(value);
        const item = document.createElement('div');
        item.className = 'component-item';
        item.innerHTML = `
            <div class="component-info">
                <span class="component-icon">${icons[key] || '⚙️'}</span>
                <span class="component-name">${componentNames[key] || key}</span>
            </div>
            <span class="component-badge ${badge.cls}">${badge.label}</span>
        `;
        statusDiv.appendChild(item);
    });
}

// ==================== FL MONITOR TAB ====================

async function updateFLMonitor() {
    await updateTrainingLogs();
    updateFLCharts();
}

async function updateTrainingLogs() {
    const logsDiv = document.getElementById('training-logs');
    if (!logsDiv) return;

    try {
        const response = await fetch(`${BACKEND_URL}/api/training_logs`);
        const logs = await response.json();

        if (!logs || logs.length === 0) {
            logsDiv.innerHTML = `
                <div class="empty-state">
                    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                        <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="2"/>
                        <circle cx="32" cy="32" r="12" fill="currentColor"/>
                        <path d="M32 8V20M32 44V56M8 32H20M44 32H56" stroke="currentColor" stroke-width="2"/>
                    </svg>
                    <p>No training rounds yet. Upload a document and trigger a round.</p>
                </div>`;
            return;
        }

        logsDiv.innerHTML = logs.map(log => `
            <div class="log-entry">
                <span class="log-time">${new Date(log.created_at).toLocaleTimeString()}</span>
                <span class="log-message">
                    Round ${log.round_no} | Client: ${log.client_id.substring(0, 8)} | ε: ${parseFloat(log.epsilon).toFixed(2)}
                </span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load training logs:', error);
    }
}

function updateFLCharts() {
    createTrainingProgressChart();
    createPrivacyBudgetChart();
}

// Uses real per-round history tracked from FL status
function createTrainingProgressChart() {
    const div = document.getElementById('training-progress-chart');
    if (!div) return;

    const { rounds, accuracy } = state.roundHistory;

    if (rounds.length === 0) {
        div.innerHTML = `<div class="chart-empty-state">
            <p style="color: var(--text-muted, #9ca3af); text-align:center; padding: 40px 0;">
                No training rounds yet.<br>Trigger a round to see progress.
            </p>
        </div>`;
        return;
    }

    // Derive loss as 1 - accuracy (standard approximation for display)
    const loss = accuracy.map(a => parseFloat((1 - a).toFixed(3)));

    const data = [{
            x: rounds,
            y: accuracy,
            name: 'Accuracy',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#10b981', width: 3 },
            marker: { size: 8 }
        },
        {
            x: rounds,
            y: loss,
            name: 'Loss',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#ef4444', width: 3 },
            marker: { size: 8 },
            yaxis: 'y2'
        }
    ];

    const layout = {
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: state.theme === 'dark' ? '#9ca3af' : '#4b5563', size: 11 },
        margin: { l: 40, r: 40, t: 10, b: 40 },
        xaxis: {
            title: 'Round',
            gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
            zeroline: false,
            dtick: 1
        },
        yaxis: {
            title: 'Accuracy',
            range: [0, 1],
            gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
            zeroline: false
        },
        yaxis2: { title: 'Loss', overlaying: 'y', side: 'right', range: [0, 1] },
        showlegend: true,
        legend: { x: 0, y: 1.1, orientation: 'h' },
        hovermode: 'x unified'
    };

    Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });
    setTimeout(() => {
        Plotly.Plots.resize(div);
    }, 100);
}

// Uses real epsilon tracked per round
function createPrivacyBudgetChart() {
    const div = document.getElementById('privacy-budget-chart');
    if (!div) return;

    const { rounds, epsilon } = state.roundHistory;

    if (rounds.length === 0) {
        div.innerHTML = `<div class="chart-empty-state">
            <p style="color: var(--text-muted, #9ca3af); text-align:center; padding: 40px 0;">
                Privacy budget will be tracked here as rounds complete.
            </p>
        </div>`;
        return;
    }

    const SAFETY_THRESHOLD = 10;
    const maxX = Math.max(...rounds);

    const data = [{
        x: rounds,
        y: epsilon,
        type: 'scatter',
        mode: 'lines+markers',
        fill: 'tozeroy',
        line: { color: '#f59e0b', width: 3 },
        marker: { size: 6 },
        fillcolor: 'rgba(245, 158, 11, 0.15)',
        name: 'ε used'
    }];

    const layout = {
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: state.theme === 'dark' ? '#9ca3af' : '#4b5563', size: 11 },
        margin: { l: 40, r: 20, t: 10, b: 40 },
        xaxis: {
            title: 'Round',
            gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
            zeroline: false,
            dtick: 1
        },
        yaxis: {
            title: 'Privacy Budget (ε)',
            gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
            zeroline: false
        },
        shapes: [{
            type: 'line',
            x0: 0,
            x1: maxX,
            y0: SAFETY_THRESHOLD,
            y1: SAFETY_THRESHOLD,
            line: { color: '#ef4444', width: 2, dash: 'dash' }
        }],
        annotations: [{
            x: maxX,
            y: SAFETY_THRESHOLD,
            text: 'Safety Threshold (ε=10)',
            showarrow: false,
            xanchor: 'right',
            font: { color: '#ef4444', size: 10 }
        }],
        hovermode: 'x unified'
    };

    Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });
}

// ==================== DASHBOARD CHARTS ====================

function initCharts(force = false) {
    if (state.currentSection !== 'dashboard') return;

    if (!state.uploadedFile) {
        createFinancialChart(currentPeriod);
        createCategoryChart();
        return;
    }

    // 🔥 PREVENT RELOAD SAME FILE
    if (!force && chartsLoadedForFile === state.uploadedFile) {
        return;
    }

    chartsLoadedForFile = state.uploadedFile;

    createFinancialChart(currentPeriod);
    createCategoryChart();
}

// Fetches from real API if file uploaded, shows empty state otherwise
async function createFinancialChart(period = 'monthly') {
    const div = document.getElementById('financial-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see your financial overview');
        return;
    }

    try {
        const res = await fetch(
            `${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}&period=${period}`
        );

        const json = await res.json();

        if (json.status !== 'success' || !json.payload) {
            renderChartEmptyState(div, 'Could not load chart data from this file');
            return;
        }

        const payload = json.payload;
        const xData = payload.x;
        const seriesData = payload.series;

        const traces = seriesData.map((s) => {
            const isDeposit = s.name.toLowerCase().includes('deposit');
            return {
                x: xData,
                y: s.values,
                name: s.name,
                type: 'bar',
                marker: {
                    color: isDeposit ? '#10b981' : '#ef4444'
                }
            };
        });

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {
                color: state.theme === 'dark' ? '#9ca3af' : '#4b5563',
                size: 11
            },
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: {
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
            },
            yaxis: {
                title: 'Amount (₹)',
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
            },
            showlegend: true,
            legend: { x: 0, y: 1.1, orientation: 'h' },
            hovermode: 'x unified',
            barmode: period !== 'daily' ? 'group' : undefined
        };

        Plotly.newPlot(div, traces, layout, {
            responsive: true,
            displayModeBar: false
        });

    } catch (err) {
        console.error('Financial chart error:', err);
        renderChartEmptyState(div, 'Failed to load chart');
    }
}

// Fetches category data from vizdata or shows empty state
async function createCategoryChart() {
    const div = document.getElementById('category-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see spending categories');
        return;
    }

    try {
        const res = await fetch(`${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.payload) {
            renderChartEmptyState(div, 'Could not derive category data from this file');
            return;
        }

        const payload = json.payload;
        const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#f97316'];

        // 🔥 Use category data from backend
        const labels = payload.categories.labels;
        const values = payload.categories.values;

        if (labels.length === 0 || values.length === 0) {
            renderChartEmptyState(div, 'No category data available');
            return;
        }

        const data = [{
            labels,
            values,
            type: 'pie',
            hole: 0.5,
            marker: { colors: colors.slice(0, labels.length) },
            textposition: 'inside',
            textinfo: 'label+percent'
        }];

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: state.theme === 'dark' ? '#e8eaed' : '#111827', size: 11 },
            margin: { l: 20, r: 20, t: 20, b: 20 },
            showlegend: false,
            hovermode: 'closest'
        };

        Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });

    } catch (err) {
        console.error('Category chart error:', err);
        renderChartEmptyState(div, 'Failed to load category chart');
    }
}

// ==================== ANALYTICS TAB ====================

async function updateAnalyticsCharts() {
    await createTimelineChart();
    await createIncomeExpenseChart();
    await createSavingsChart();
    createMerchantsChart();
    await createCategoryBreakdownChart();
}

async function createTimelineChart() {
    const div = document.getElementById('timeline-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see transaction timeline');
        return;
    }

    try {
        const res = await fetch(`${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}`);
        const json = await res.json();

        if (json.status !== 'success') {
            renderChartEmptyState(div, 'Could not load timeline from this file');
            return;
        }

        const payload = json.payload;
        // Use first series as the main timeline
        const series = payload.series[0];

        const data = [{
            x: payload.x,
            y: series.values,
            type: 'scatter',
            mode: 'lines',
            fill: 'tozeroy',
            name: series.name,
            line: { color: '#3b82f6', width: 3 },
            fillcolor: 'rgba(59, 130, 246, 0.15)'
        }];

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: state.theme === 'dark' ? '#9ca3af' : '#4b5563', size: 11 },
            margin: { l: 50, r: 20, t: 10, b: 60 },
            xaxis: {
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
                tickangle: -45
            },
            yaxis: {
                title: 'Amount (₹)',
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
            },
            hovermode: 'x unified'
        };

        Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });

    } catch (err) {
        console.error('Timeline chart error:', err);
        renderChartEmptyState(div, 'Failed to load timeline');
    }
}

async function createIncomeExpenseChart() {
    const div = document.getElementById('income-expense-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see income vs expenses');
        return;
    }

    try {
        const res = await fetch(`${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}`);
        const json = await res.json();

        if (json.status !== 'success') {
            renderChartEmptyState(div, 'Could not load data from this file');
            return;
        }

        const payload = json.payload;
        const colors = ['#10b981', '#ef4444', '#3b82f6', '#f59e0b'];

        const traces = payload.series.map((s, i) => ({
            x: payload.x,
            y: s.values,
            name: s.name,
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: colors[i % colors.length], width: 3 }
        }));

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: state.theme === 'dark' ? '#9ca3af' : '#4b5563', size: 11 },
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: { gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
            yaxis: {
                title: 'Amount (₹)',
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
            },
            legend: { x: 0, y: 1.1, orientation: 'h' },
            hovermode: 'x unified'
        };

        Plotly.newPlot(div, traces, layout, { responsive: true, displayModeBar: false });

    } catch (err) {
        renderChartEmptyState(div, 'Failed to load chart');
    }
}

async function createSavingsChart() {
    const div = document.getElementById('savings-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see savings rate');
        return;
    }

    try {
        const res = await fetch(`${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}`);
        const json = await res.json();

        if (json.status !== 'success' || json.payload.series.length < 2) {
            renderChartEmptyState(div, 'Need credit & debit columns to compute savings');
            return;
        }

        const payload = json.payload;
        // Savings = first series - second series (credit - debit)
        const s1 = payload.series[0].values;
        const s2 = payload.series[1].values;
        const savings = s1.map((v, i) => parseFloat((v - (s2[i] || 0)).toFixed(2)));

        const data = [{
            x: payload.x,
            y: savings,
            type: 'bar',
            name: 'Net Savings',
            marker: {
                color: savings.map(v => v >= 0 ? '#10b981' : '#ef4444')
            }
        }];

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: state.theme === 'dark' ? '#9ca3af' : '#4b5563', size: 11 },
            margin: { l: 50, r: 20, t: 10, b: 40 },
            xaxis: { gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
            yaxis: {
                title: 'Net Savings (₹)',
                gridcolor: state.theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'
            },
            hovermode: 'x unified'
        };

        Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });

    } catch (err) {
        renderChartEmptyState(div, 'Failed to compute savings');
    }
}

// Merchants chart — only meaningful from real uploaded data
function createMerchantsChart() {
    const div = document.getElementById('merchants-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see top merchants');
        return;
    }

    // Merchant breakdown requires description column parsing — show honest message
    renderChartEmptyState(div, 'Merchant analysis requires a "Description" or "Merchant" column in your CSV');
}

async function createCategoryBreakdownChart() {
    const div = document.getElementById('category-breakdown-chart');
    if (!div) return;

    if (!state.uploadedFile) {
        renderChartEmptyState(div, 'Upload a document to see category breakdown');
        return;
    }

    try {
        const res = await fetch(`${BACKEND_URL}/api/vizdata?filename=${encodeURIComponent(state.uploadedFile)}`);
        const json = await res.json();

        if (json.status !== 'success' || !json.payload) {
            renderChartEmptyState(div, 'Could not load category breakdown');
            return;
        }

        const payload = json.payload;
        const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#f97316'];

        const labels = payload.categories.labels;
        const values = payload.categories.values;

        if (labels.length === 0 || values.length === 0) {
            renderChartEmptyState(div, 'No category breakdown available');
            return;
        }

        const data = [{
            labels,
            values,
            type: 'pie',
            marker: { colors: colors.slice(0, labels.length) },
            textinfo: 'label+percent'
        }];

        const layout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: state.theme === 'dark' ? '#e8eaed' : '#111827', size: 11 },
            margin: { l: 20, r: 20, t: 20, b: 20 },
            showlegend: true,
            legend: { x: 0, y: 0 }
        };

        Plotly.newPlot(div, data, layout, { responsive: true, displayModeBar: false });
    } catch (err) {
        console.error('Category breakdown error:', err);
        renderChartEmptyState(div, 'Failed to load category breakdown');
    }
}

// ==================== DASHBOARD DATA ====================

async function loadDashboardData() {
    // Stats are loaded from FL status — no random numbers
    // Kick off the first FL status fetch which populates all stat cards
    await updateFLStatus();
}

// ==================== CHART HELPERS ====================

function renderChartEmptyState(div, message) {
    div.innerHTML = `
        <div style="
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 100%; min-height: 160px; color: var(--text-muted, #9ca3af);
            text-align: center; padding: 20px; gap: 10px;
        ">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity="0.4">
                <rect x="4" y="24" width="6" height="12" stroke="currentColor" stroke-width="2"/>
                <rect x="14" y="16" width="6" height="20" stroke="currentColor" stroke-width="2"/>
                <rect x="24" y="8" width="6" height="28" stroke="currentColor" stroke-width="2"/>
                <rect x="34" y="20" width="6" height="16" stroke="currentColor" stroke-width="2"/>
            </svg>
            <p style="font-size: 13px; margin: 0;">${message}</p>
        </div>`;
}

function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// ==================== FILE UPLOAD ====================

function openFileUpload() {
    document.getElementById('file-upload').click();
}

async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('File too large. Maximum size is 16MB', 'error');
        return;
    }

    const validTypes = ['pdf', 'csv', 'xlsx', 'xls'];
    const ext = file.name.split('.').pop().toLowerCase();
    if (!validTypes.includes(ext)) {
        showToast('Invalid file type. Use PDF, CSV, or XLSX', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    showToast(`Uploading ${file.name}...`, 'info');

    try {
        const response = await fetch(`${BACKEND_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.status === 'success') {
            state.uploadedFile = data.data.saved_filename;
            state.fileType = data.data.file_type;

            showToast(`${file.name} uploaded successfully!`, 'success');
            document.getElementById('attachment-name').textContent = file.name;
            document.getElementById('file-attachment').style.display = 'flex';

            addChatMessage(`📎 File uploaded: ${file.name}`, 'bot');

            // Refresh dashboard charts with real data now that file is available
            if (state.currentSection === 'dashboard') {
                chartsLoadedForFile = null; // reset
                initCharts(true);
            }

            if (state.currentSection !== 'chat') {
                navigateToSection('chat');
            }
        } else {
            showToast(data.message || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Network error. Please try again.', 'error');
        console.error('Upload error:', error);
    }
}

function removeAttachment() {
    state.uploadedFile = null;
    state.fileType = null;
    document.getElementById('file-attachment').style.display = 'none';
    // Reset charts to empty state
    if (state.currentSection === 'dashboard') initCharts();
}

// ==================== CHAT ====================

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    addChatMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';

    const typingDiv = addTypingIndicator();

    try {
        const response = await fetch(`${BACKEND_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, filename: state.uploadedFile })
        });

        const data = await response.json();
        typingDiv.remove();

        if (data.status === 'success') {
            addChatMessage(data.data.reply, 'bot', true);
        } else {
            addChatMessage('Failed to get response. Please try again.', 'bot');
        }
    } catch (error) {
        typingDiv.remove();
        addChatMessage('Network error. Please check your connection.', 'bot');
        console.error('Chat error:', error);
    }
}

function addChatMessage(text, sender, isHTML = false) {
    const messagesDiv = document.getElementById('chat-messages');
    const welcomeMsg = messagesDiv.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    const avatar = sender === 'user' ? '👤' : '🤖';

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">${isHTML ? text : escapeHtml(text)}</div>
            <div class="message-time">${time}</div>
        </div>`;

    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    state.chatHistory.push({ text, sender, time });
}

function addTypingIndicator() {
    const messagesDiv = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'message bot';
    div.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
            </div>
        </div>`;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return div;
}

function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResizeTextarea(event) {
    const textarea = event.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function quickAction(action) {
    if (action === 'visualize') {
        if (!state.uploadedFile) {
            showToast("Upload a document first", "warning");
            return;
        }

        navigateToSection('dashboard');
        initCharts();
        showToast("Dashboard loaded", "success");
        return;
    }

    const prompts = {
        'analyze': 'Analyze this financial report',
        'train': 'Submit encrypted financial data for federated model training'
    };

    const input = document.getElementById('chat-input');
    input.value = prompts[action] || '';
    input.focus();
}

function usePrompt(prompt) {
    // 🔥 SPECIAL CASE: DASHBOARD PROMPT
    if (prompt.toLowerCase().includes("dashboard")) {
        if (!state.uploadedFile) {
            showToast("Upload a document first", "warning");
            return;
        }

        // 🔥 SWITCH TO DASHBOARD
        navigateToSection('dashboard');

        // 🔥 LOAD REAL DATA (NO LLM)
        initCharts();

        showToast("Dashboard generated from real data", "success");
        return;
    }

    const input = document.getElementById('chat-input');
    input.value = prompt;
    input.focus();
}

// ==================== FL ACTIONS ====================

async function triggerFLRound() {
    if (triggeringRound) return;
    triggeringRound = true;
    showToast('Triggering FL training round...', 'info');

    try {
        const response = await fetch(`${BACKEND_URL}/api/trigger_round`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.status === 'success') {
            showToast(`Round ${data.round} complete — Accuracy: ${(data.accuracy * 100).toFixed(1)}% | ε: ${data.epsilon.toFixed(2)}`, 'success');
            setTimeout(() => {
                updateFLStatus();
                updateFLMonitor();
            }, 1000);
        } else {
            showToast(data.message || 'Failed to trigger round', 'error');
        }
    } catch (error) {
        console.error('FL trigger error:', error);
        showToast('Network error while triggering round', 'error');
    } finally {
        triggeringRound = false;
    }
}

async function submitFeaturesForTraining() {
    if (!state.uploadedFile) {
        showToast('Please upload a document first', 'warning');
        return;
    }
    navigateToSection('chat');
    const input = document.getElementById('chat-input');
    input.value = 'Submit my data for FL training';
    sendMessage();
}

function refreshTrainingLogs() {
    showToast('Refreshing training logs...', 'info');
    updateTrainingLogs();
}

// ==================== CHART CONTROLS ====================

function refreshCategoryChart() {
    createCategoryChart();
    showToast('Chart refreshed', 'success');
}

function updateFinancialChart(period) {
    currentPeriod = period
    createFinancialChart(period);
    if (state.uploadedFile) {
        showToast(`Chart updated for ${period}`, 'info');
    } else {
        showToast('Upload a document to filter by period', 'warning');
    }
}

function changeChartType(chart, type) {
    showToast(`Chart type selection coming soon`, 'info');
}

// ==================== QUICK ACTIONS ====================

function downloadModel() {
    showToast('Model export — coming soon', 'info');
}

function viewAuditLogs() {
    showToast('Opening audit logs — coming soon', 'info');
}

function exportMetrics() {
    // Export real FL status as JSON
    const metrics = {
        fl_status: state.flStatus,
        round_history: state.roundHistory,
        exported_at: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(metrics, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fingpt_metrics_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Metrics exported successfully', 'success');
}

// ==================== AUTH ====================

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}

// ==================== TOAST ====================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `
        <span style="font-size: 18px;">${icons[type] || 'ℹ'}</span>
        <span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==================== UTILS ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}