// -----------------------------
// FINGPT Frontend Logic
// -----------------------------
const msgBox = document.getElementById("messages");
const fileInput = document.getElementById("fileInput");
const attachBtn = document.getElementById("attachBtn");
const sendBtn = document.getElementById("sendBtn");
const messageInput = document.getElementById("messageInput");
let uploadedFile = null;

// ---------- THEME TOGGLE ----------
const themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  // Initialize saved theme
  const saved = localStorage.getItem("fingpt_theme");
  if (saved === "light") document.body.classList.remove("dark");
  themeToggle.checked = saved === "light";

  themeToggle.addEventListener("change", (e) => {
    if (e.target.checked) {
      document.body.classList.remove("dark");
      localStorage.setItem("fingpt_theme", "light");
    } else {
      document.body.classList.add("dark");
      localStorage.setItem("fingpt_theme", "dark");
    }
  });
}

// ---------- LOGIN / SIGNUP DEMO ----------
function fakeLogin() {
  // TODO: replace with real auth
  window.location.href = "/dashboard";
}
function fakeSignup() {
  window.location.href = "/dashboard";
}

// ---------- FILE UPLOAD ----------
if (attachBtn) attachBtn.addEventListener("click", () => fileInput.click());
if (fileInput) fileInput.addEventListener("change", uploadFile);

function uploadFile() {
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  addMessage(`📎 Uploaded: ${file.name}`, "user");

  fetch("/api/upload", {
    method: "POST",
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "ok") {
        uploadedFile = data.filename;
        addMessage(`✅ File ${data.filename} uploaded successfully.`, "bot");
        addMessage("You can now choose: Visualization, Bank Statement Analysis, or Payslip Analysis.", "bot");
        showActionsForFile(data);
      } else {
        addMessage(`❌ ${data.error}`, "bot");
      }
    })
    .catch(err => {
      console.error(err);
      addMessage("⚠️ Upload failed.", "bot");
    });
}

// ---------- CHAT ----------
if (sendBtn) sendBtn.addEventListener("click", sendMessage);
if (messageInput) messageInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});

function sendMessage() {
  const msg = messageInput.value.trim();
  if (!msg) return;
  addMessage(msg, "user");
  messageInput.value = "";

  // show temporary loader
  const loader = addMessage("Thinking...", "bot", true);

  fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ message: msg, filename: uploadedFile })
  })
    .then(res => res.json())
    .then(data => {
      // remove loader
      if (loader) loader.remove();
      addMessage(data.reply, "bot");
    })
    .catch(err => {
      console.error(err);
      if (loader) loader.remove();
      addMessage("⚠️ Error contacting server.", "bot");
    });
}

function addMessage(text, sender="bot", asLoader=false) {
  const div = document.createElement("div");
  div.className = "msg " + (sender === "user" ? "user" : "bot");
  div.innerText = text;
  if (asLoader) div.dataset.loader = "1";
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
  return div;
}

// ---------- DRAG & DROP ----------
const chatWindow = document.getElementById("chatWindow");
if (chatWindow) {
  chatWindow.addEventListener("dragover", (e) => {
    e.preventDefault();
    chatWindow.style.border = "2px dashed var(--accent)";
  });
  chatWindow.addEventListener("dragleave", (e) => {
    e.preventDefault();
    chatWindow.style.border = "none";
  });
  chatWindow.addEventListener("drop", (e) => {
    e.preventDefault();
    chatWindow.style.border = "none";
    const file = e.dataTransfer.files[0];
    if (file) {
      fileInput.files = e.dataTransfer.files;
      uploadFile();
    }
  });
}

// ---------- UI helpers ----------
function showActionsForFile(data){
  // show action buttons in viz area (simple)
  const actions = data.actions || {};
  const vizArea = document.getElementById("vizArea");
  vizArea.innerHTML = "";
  const wrapper = document.createElement("div");
  wrapper.style.padding = "12px";
  if (actions.visualization) {
    const vizBtn = document.createElement("button");
    vizBtn.className = "small-btn";
    vizBtn.innerText = "Open Visualization Dashboard";
    vizBtn.onclick = openVisualization;
    wrapper.appendChild(vizBtn);
  }
  if (Array.isArray(actions.analyses)) {
    actions.analyses.forEach(a => {
      const b = document.createElement("button");
      b.className = "small-btn";
      b.style.marginLeft = "8px";
      b.innerText = a;
      b.onclick = () => startAnalysis(a.toLowerCase().includes("bank") ? "bank" : "payslip", data.filename);
      wrapper.appendChild(b);
    });
  }
  vizArea.appendChild(wrapper);
}

// ---------- PLACEHOLDER ACTIONS ----------
function startAnalysis(type, filename) {
  if (!uploadedFile && !filename) {
    addMessage("Please upload a CSV or PDF first.", "bot");
    return;
  }
  const targetFile = filename || uploadedFile;
  addMessage(`Starting ${type} analysis for ${targetFile}`, "user");
  const loader = addMessage("Analyzing...", "bot", true);
  fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ message: `${type} analysis`, filename: targetFile })
  })
    .then(res => res.json())
    .then(data => {
      if (loader) loader.remove();
      addMessage(data.reply, "bot");
      const vizArea = document.getElementById("vizArea");
      vizArea.innerHTML = `<div style="padding:12px;"><strong>${type.toUpperCase()} ANALYSIS</strong><div style="margin-top:10px;" class="viz-placeholder">[Chart placeholder — integrate Chart.js or Plotly]</div></div>`;
      document.getElementById("visualPreview").removeAttribute("aria-hidden");
    })
    .catch(err => {
      console.error(err);
      if (loader) loader.remove();
      addMessage("Analysis failed (network).", "bot");
    });
}

function openVisualization() {
  const viz = document.getElementById("vizArea");
  viz.innerHTML = "<div class='viz-placeholder'>📊 Visualization Placeholder — integrate Chart.js or Plotly later.</div>";
  document.getElementById("visualPreview").removeAttribute("aria-hidden");
  addMessage("Opened visualization dashboard.", "bot");
}
