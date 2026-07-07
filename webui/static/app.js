const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const endSessionBtn = document.getElementById("end-session-btn");

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Auto-links bare URLs so article citations from the agent are clickable.
function linkify(text) {
  return escapeHtml(text).replace(
    /(https?:\/\/[^\s)]+)/g,
    (url) => `<a href="${url}" target="_blank" rel="noopener">${url}</a>`
  );
}

function addMessage(role, text, { pending = false } = {}) {
  const row = document.createElement("div");
  row.className = `msg ${role}${pending ? " pending" : ""}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = linkify(text);
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return row;
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = "";
  inputEl.disabled = true;
  addMessage("user", text);
  const pendingRow = addMessage("agent", "Thinking…", { pending: true });

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await resp.json();
    pendingRow.remove();
    if (!resp.ok) {
      addMessage("agent", `Error: ${data.error || "something went wrong"}`);
    } else {
      addMessage("agent", data.reply || "(no response)");
    }
  } catch (err) {
    pendingRow.remove();
    addMessage("agent", `Error: ${err.message}`);
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});

endSessionBtn.addEventListener("click", async () => {
  endSessionBtn.disabled = true;
  endSessionBtn.textContent = "Saving…";
  try {
    await fetch("/api/end_session", { method: "POST" });
    messagesEl.innerHTML = "";
    addMessage("agent", "Session saved. Starting a new conversation.");
  } finally {
    endSessionBtn.disabled = false;
    endSessionBtn.textContent = "End session & save";
  }
});

async function loadMemory(name, elementId, emptyText) {
  const el = document.getElementById(elementId);
  try {
    const resp = await fetch(`/api/memory/${name}`);
    const data = await resp.json();
    el.textContent = (data.content || "").trim() || emptyText;
    el.classList.remove("muted");
    el.innerHTML = linkify(el.textContent);
  } catch (err) {
    el.textContent = "Failed to load.";
  }
}

async function loadReports() {
  const el = document.getElementById("reports-list");
  try {
    const resp = await fetch("/api/reports");
    const data = await resp.json();
    if (!data.reports || data.reports.length === 0) {
      el.textContent = "No reports yet.";
      return;
    }
    el.innerHTML = "";
    for (const name of data.reports) {
      const link = document.createElement("a");
      link.href = `/reports/${name}`;
      link.target = "_blank";
      link.textContent = name;
      link.style.display = "block";
      el.appendChild(link);
    }
  } catch (err) {
    el.textContent = "Failed to load.";
  }
}

loadMemory("top_of_mind", "top-of-mind", "No highlights yet.");
loadMemory("session", "session-info", "No pipeline runs yet.");
loadReports();
inputEl.focus();
