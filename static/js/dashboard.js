// ========================================================
// FINGPT Frontend Logic — Modernized Dashboard JS
// ========================================================

// ---------- ELEMENT REFERENCES ----------
const msgBox = document.getElementById("messages");
const fileInput = document.getElementById("fileInput");
const attachBtn = document.getElementById("attachBtn");
const sendBtn = document.getElementById("sendBtn");
const messageInput = document.getElementById("messageInput");
const chatWindow = document.getElementById("chatWindow");
let uploadedFile = null;

// ---------- THEME TOGGLE ----------
document.getElementById("themeToggle")?.addEventListener("change", (e) => {
  document.body.classList.toggle("dark");
});

// ---------- HELPER FUNCTIONS ----------
function addMessage(text, sender = "bot") {
  const div = document.createElement("div");
  div.className = `msg ${sender}`;
  div.innerHTML = text;
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
}

function showTyping() {
  const typing = document.createElement("div");
  typing.className = "msg bot typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  msgBox.appendChild(typing);
  msgBox.scrollTop = msgBox.scrollHeight;
  return typing;
}

function delay(ms) {
  return new Promise(res => setTimeout(res, ms));
}

// ---------- FILE UPLOAD ----------
attachBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", uploadFile);

async function uploadFile() {
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  addMessage(`📎 Uploading: <b>${file.name}</b>`, "user");
  showTyping();

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    document.querySelector(".typing")?.remove();

    if (data.status === "ok") {
      uploadedFile = data.saved_as;
      addMessage(`✅ <b>${data.original}</b> uploaded successfully.`, "bot");

      let options = "";
      if (data.actions.visualization)
        options += `<button class="mini-btn" onclick="openVisualization()">Visualization</button>`;
      (data.actions.analyses || []).forEach(a => {
        options += `<button class="mini-btn" onclick="startAnalysis('${a}')">${a}</button>`;
      });

      addMessage(`Choose an action:<br>${options}`, "bot");
    } else {
      addMessage(`❌ ${data.message || "Upload failed."}`, "bot");
    }
  } catch (err) {
    console.error(err);
    addMessage("⚠️ Upload failed — please try again.", "bot");
  }
}

// ---------- CHAT ----------
sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const msg = messageInput.value.trim();
  if (!msg) return;

  addMessage(msg, "user");
  messageInput.value = "";
  const typing = showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, filename: uploadedFile })
    });
    const data = await res.json();
    typing.remove();
    addMessage(data.reply || "⚠️ No reply received.", "bot");
  } catch (err) {
    typing.remove();
    addMessage("⚠️ Server not responding.", "bot");
  }
}

// ---------- DRAG & DROP ----------
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
    uploadFile();
  }
});

// ---------- QUICK ACTIONS ----------
async function startAnalysis(type) {
  if (!uploadedFile) {
    addMessage("⚠️ Please upload a file first.", "bot");
    return;
  }
  addMessage(`Starting ${type} for ${uploadedFile}...`, "user");
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: `${type} analysis`, filename: uploadedFile })
    });
    const data = await res.json();
    document.querySelector(".typing")?.remove();
    addMessage(data.reply || "Analysis complete.", "bot");
  } catch {
    addMessage("⚠️ Error during analysis.", "bot");
  }
}

async function openVisualization() {
  if (!uploadedFile) {
    addMessage("⚠️ Upload a CSV file first for visualization.", "bot");
    return;
  }

  addMessage("Fetching preview and visualization data...", "bot");
  showTyping();

  try {
    const [previewRes, vizRes] = await Promise.all([
      fetch(`/api/preview?filename=${encodeURIComponent(uploadedFile)}&rows=5`),
      fetch("/api/vizdata")
    ]);

    const previewData = await previewRes.json();
    const vizData = await vizRes.json();
    document.querySelector(".typing")?.remove();

    if (previewData.status !== "ok") {
      addMessage(`⚠️ ${previewData.message}`, "bot");
      return;
    }

    renderPreview(previewData);
    renderChart(vizData.payload);
  } catch (err) {
    console.error(err);
    addMessage("⚠️ Visualization fetch failed.", "bot");
  }
}

// ---------- RENDER FUNCTIONS ----------
function renderPreview(data) {
  const viz = document.getElementById("vizArea");
  const table = document.createElement("table");
  table.className = "preview-table";

  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${data.columns.map(c => `<th>${c}</th>`).join("")}</tr>`;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  data.rows.forEach(r => {
    const row = document.createElement("tr");
    row.innerHTML = r.map(v => `<td>${v}</td>`).join("");
    tbody.appendChild(row);
  });
  table.appendChild(tbody);

  viz.innerHTML = `<h3>CSV Preview</h3>`;
  viz.appendChild(table);
  document.getElementById("visualPreview").removeAttribute("aria-hidden");
  addMessage("📊 CSV preview generated successfully.", "bot");
}

function renderChart(data) {
  if (!window.Plotly) {
    addMessage("⚠️ Visualization requires Plotly.js (add via CDN).", "bot");
    return;
  }

  const viz = document.getElementById("vizArea");
  const chartDiv = document.createElement("div");
  chartDiv.id = "chartDiv";
  viz.appendChild(chartDiv);

  const traces = data.series.map(s => ({
    x: data.x,
    y: s.values,
    mode: "lines+markers",
    name: s.name
  }));

  Plotly.newPlot("chartDiv", traces, {
    title: data.title,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#ccc" }
  });
}
