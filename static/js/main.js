// =========================================================
// FINGPT - Enhanced Financial Analyzer Dashboard
// Version 2.0 | Production-Ready Implementation
// =========================================================

// ---------- DOM REFERENCES ----------
const msgBox = document.getElementById("messages");
const fileInput = document.getElementById("fileInput");
const attachBtn = document.getElementById("attachBtn");
const sendBtn = document.getElementById("sendBtn");
const messageInput = document.getElementById("messageInput");
const chatWindow = document.getElementById("chatWindow");
const vizArea = document.getElementById("vizArea");
const visualPreview = document.getElementById("visualPreview");

// ---------- STATE MANAGEMENT ----------
let state = {
    uploadedFile: null,
    uploadedFileId: null,
    fileType: null,
    chatHistory: [],
    theme: 'dark'
};

async function parseApiResponse(response) {
    const rawText = await response.text();
    let data = {};

    try {
        data = rawText ? JSON.parse(rawText) : {};
    } catch (error) {
        throw new Error(rawText || `Unexpected ${response.status} response from server.`);
    }

    if (!response.ok || data.status === "error") {
        throw new Error(data.message || `Request failed with status ${response.status}.`);
    }

    return data;
}

// ---------- THEME MANAGEMENT ----------
function initTheme() {
    // Check theme preference from body class instead of localStorage
    const isDark = document.body.classList.contains('dark');
    state.theme = isDark ? 'dark' : 'light';

    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        themeToggle.checked = !isDark;
        themeToggle.addEventListener("change", (e) => {
            if (e.target.checked) {
                document.body.classList.remove("dark");
                state.theme = 'light';
            } else {
                document.body.classList.add("dark");
                state.theme = 'dark';
            }
        });
    }
}

// ---------- MESSAGE SYSTEM ----------
function addMessage(text, sender = "bot", options = {}) {
    const div = document.createElement("div");
    div.className = `msg ${sender}`;

    if (options.isHTML) {
        div.innerHTML = text;
    } else {
        div.textContent = text;
    }

    if (options.isTyping) {
        div.classList.add('typing');
        div.innerHTML = '<span></span><span></span><span></span>';
    }

    msgBox.appendChild(div);
    msgBox.scrollTop = msgBox.scrollHeight;

    // Add to history
    if (!options.isTyping) {
        state.chatHistory.push({ text, sender, timestamp: Date.now() });
    }

    return div;
}

function showTyping() {
    return addMessage("", "bot", { isTyping: true });
}

function removeTyping() {
    const typing = msgBox.querySelector('.typing');
    if (typing) typing.remove();
}

// ---------- FILE UPLOAD ----------
if (attachBtn) {
    attachBtn.addEventListener("click", () => fileInput.click());
}

if (fileInput) {
    fileInput.addEventListener("change", handleFileUpload);
}

async function handleFileUpload() {
    const file = fileInput.files[0];
    if (!file) return;

    // Validate file size (16MB)
    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
        addMessage("❌ File too large. Maximum size is 16MB.", "bot");
        return;
    }

    // Validate file type
    const validTypes = ['pdf', 'csv', 'xlsx'];
    const fileExt = file.name.split('.').pop().toLowerCase();
    if (!validTypes.includes(fileExt)) {
        addMessage("❌ Unsupported file type. Please upload PDF, CSV, or XLSX.", "bot");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    addMessage(`📎 Uploading: ${file.name}`, "user");
    const typing = showTyping();

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        const data = await parseApiResponse(response);
        removeTyping();

        console.log("Upload response:", data); // Debug log

        if (data.status === "success") {
            state.uploadedFile = data.data.saved_filename;
            state.uploadedFileId = data.data.file_id;
            state.fileType = data.data.file_type;

            const sizeKB = (data.data.file_size / 1024).toFixed(1);
            addMessage(`✅ **${data.data.original_filename}** uploaded successfully! (${sizeKB} KB)`, "bot", { isHTML: true });

            // Show available actions
            displayActions(data.data.actions, data.data.original_filename);
        } else {
            addMessage(`❌ Upload failed: ${data.message || "Unknown error"}`, "bot");
        }
    } catch (error) {
        removeTyping();
        addMessage(error.message || "Upload failed. Please try again.", "bot");
        console.error("Upload error:", error);
    }
}

// ---------- ACTION BUTTONS ----------
function displayActions(actions, filename) {
    if (!actions) return;

    let html = '<div class="action-buttons" style="margin: 10px 0;">';
    html += `<p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.5rem;">Choose an action for <strong>${filename || 'your file'}</strong>:</p>`;

    if (actions.visualization) {
        html += '<button class="mini-btn" onclick="openVisualization()">📊 Visualization</button>';
    }

    if (Array.isArray(actions.analyses)) {
        actions.analyses.forEach(analysis => {
            html += `<button class="mini-btn" onclick="startAnalysis('${analysis}')">${analysis}</button>`;
        });
    }

    html += '</div>';

    addMessage(html, "bot", { isHTML: true });
}

// ---------- CHAT FUNCTIONALITY ----------
if (sendBtn) {
    sendBtn.addEventListener("click", sendMessage);
}

if (messageInput) {
    messageInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function sendMessage() {
    const msg = messageInput.value.trim();
    if (!msg) return;

    addMessage(msg, "user");
    messageInput.value = "";

    const typing = showTyping();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: msg,
                filename: state.uploadedFile, file_id: state.uploadedFileId })
        });

        const data = await parseApiResponse(response);
        removeTyping();

        addMessage(data.data.reply || "No response received.", "bot", { isHTML: true });
    } catch (error) {
        removeTyping();
        addMessage(error.message || "Failed to send message. Please try again.", "bot");
        console.error("Chat error:", error);
    }
}

// ---------- DRAG & DROP ----------
if (chatWindow) {
    chatWindow.addEventListener("dragover", (e) => {
        e.preventDefault();
        chatWindow.classList.add("dragging");
    });

    chatWindow.addEventListener("dragleave", (e) => {
        e.preventDefault();
        chatWindow.classList.remove("dragging");
    });

    chatWindow.addEventListener("drop", (e) => {
        e.preventDefault();
        chatWindow.classList.remove("dragging");

        const file = e.dataTransfer.files[0];
        if (file) {
            fileInput.files = e.dataTransfer.files;
            handleFileUpload();
        }
    });
}

// ---------- ANALYSIS FUNCTIONS ----------
async function startAnalysis(type) {
    if (!state.uploadedFile) {
        addMessage("⚠️ Please upload a file first.", "bot");
        return;
    }

    // Map analysis types to specific messages
    const analysisMap = {
        'Bank Statement Analysis': 'bank statement analysis',
        'Payslip Analysis': 'payslip analysis',
        'Data Analysis': 'data analysis',
        'Statistical Summary': 'statistical summary'
    };

    const analysisMessage = analysisMap[type] || type.toLowerCase();

    addMessage(`Starting ${type}...`, "user");
    const typing = showTyping();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: analysisMessage,
                filename: state.uploadedFile, file_id: state.uploadedFileId })
        });

        const data = await parseApiResponse(response);
        removeTyping();

        addMessage(data.data.reply || "Analysis complete.", "bot", { isHTML: true });
    } catch (error) {
        removeTyping();
        addMessage(error.message || "Analysis failed. Please try again.", "bot");
        console.error("Analysis error:", error);
    }
}

async function openVisualization() {
    if (!state.uploadedFile) {
        addMessage("⚠️ Please upload a CSV file first.", "bot");
        return;
    }

    if (state.fileType === 'pdf') {
        addMessage("⚠️ Visualization is only available for CSV files. Your PDF has been uploaded - try 'Bank Statement Analysis' instead!", "bot");
        return;
    }

    addMessage("Generating visualization...", "bot");
    const typing = showTyping();

    try {
        const [previewRes, vizRes] = await Promise.all([
            fetch(`/api/preview?filename=${encodeURIComponent(state.uploadedFile)}&rows=10`),
            fetch("/api/vizdata")
        ]);

        const previewData = await previewRes.json();
        const vizData = await vizRes.json();

        removeTyping();

        if (previewData.status === "ok") {
            renderPreview(previewData);
            renderChart(vizData.payload);
            addMessage("✅ Visualization generated successfully!", "bot");
        } else {
            addMessage(`⚠️ ${previewData.message || "Visualization failed"}`, "bot");
        }
    } catch (error) {
        removeTyping();
        addMessage("⚠️ Failed to generate visualization.", "bot");
        console.error("Visualization error:", error);
    }
}

// ---------- RENDERING FUNCTIONS ----------
function renderPreview(data) {
    if (!vizArea) return;

    vizArea.innerHTML = '<h3 style="margin-bottom: 1rem;">📄 Data Preview</h3>';

    const table = document.createElement("table");
    table.className = "preview-table";

    // Header
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    data.columns.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement("tbody");
    data.rows.forEach(row => {
        const tr = document.createElement("tr");
        row.forEach(cell => {
            const td = document.createElement("td");
            td.textContent = cell !== null && cell !== undefined ? cell : 'N/A';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    vizArea.appendChild(table);

    if (visualPreview) {
        visualPreview.style.display = 'block';
        visualPreview.removeAttribute('aria-hidden');
    }
}

function renderChart(data) {
    if (!window.Plotly) {
        console.warn("Plotly.js not loaded. Skipping chart rendering.");
        return;
    }

    if (!vizArea) return;

    const chartContainer = document.createElement("div");
    chartContainer.style.marginTop = "2rem";

    const chartTitle = document.createElement("h3");
    chartTitle.textContent = "📊 Financial Visualization";
    chartTitle.style.marginBottom = "1rem";

    const chartDiv = document.createElement("div");
    chartDiv.id = "plotlyChart";
    chartDiv.style.width = "100%";
    chartDiv.style.height = "400px";

    chartContainer.appendChild(chartTitle);
    chartContainer.appendChild(chartDiv);
    vizArea.appendChild(chartContainer);

    // Create traces
    const traces = data.series.map(series => ({
        x: data.x,
        y: series.values,
        mode: 'lines+markers',
        name: series.name,
        line: { width: 3 },
        marker: { size: 8 }
    }));

    // Layout configuration
    const layout = {
        title: {
            text: data.title || 'Financial Overview',
            font: { size: 18, color: state.theme === 'dark' ? '#e6edf3' : '#111' }
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: state.theme === 'dark' ? '#d1d5db' : '#333' },
        xaxis: {
            gridcolor: state.theme === 'dark' ? '#2d333b' : '#e5e7eb',
            title: 'Month'
        },
        yaxis: {
            gridcolor: state.theme === 'dark' ? '#2d333b' : '#e5e7eb',
            title: 'Amount (₹)'
        },
        hovermode: 'x unified'
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false
    };

    Plotly.newPlot('plotlyChart', traces, layout, config);
}

// ---------- UTILITY FUNCTIONS ----------
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(amount);
}

function clearChat() {
    msgBox.innerHTML = '';
    state.chatHistory = [];
    addMessage("Chat cleared. How can I help you?", "bot");
}

// ---------- INITIALIZATION ----------
document.addEventListener('DOMContentLoaded', () => {
    initTheme();

    // Welcome message
    addMessage("👋 Welcome to FINGPT! Upload a financial document to get started.", "bot");

    console.log("✅ FINGPT Dashboard initialized");
});

// Export functions for inline onclick handlers
window.startAnalysis = startAnalysis;
window.openVisualization = openVisualization;
window.clearChat = clearChat;

