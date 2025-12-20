/* eslint-disable no-console */
function $(id) {
  return document.getElementById(id);
}

function setStatus(message, tone = "info") {
  const el = $("status");
  if (!el) return;
  el.textContent = message;
  el.className = `status ${tone}`;
  el.hidden = !message;
}

function setChatStatus(text) {
  const el = $("chatStatus");
  if (el) el.textContent = text;
}

async function fetchJSON(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `HTTP ${resp.status}`);
  }
  return resp.json();
}

let lastMessageId = null;
let pollTimer = null;

function renderMessage(message) {
  const wrapper = document.createElement("div");
  wrapper.className = `chat-row chat-${message.role}`;

  const header = document.createElement("div");
  header.className = "chat-meta";
  header.textContent = message.role === "user" ? "Користувач" : message.author || "Агент";
  wrapper.appendChild(header);

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = message.text || message.content || "";
  wrapper.appendChild(bubble);

  return wrapper;
}

function renderHistory(history) {
  const container = $("chatHistory");
  if (!container) return;
  container.innerHTML = "";
  history.forEach((message) => container.appendChild(renderMessage(message)));
  container.scrollTop = container.scrollHeight;
}

async function loadHistory() {
  try {
    const data = await fetchJSON(`/chat/history?after=${encodeURIComponent(lastMessageId || "")}`);
    const history = data.history || [];
    if (history.length) {
      lastMessageId = history[history.length - 1].id;
    }
    renderHistory(history);
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити історію", "error");
  }
}

async function sendMessage(event) {
  event?.preventDefault?.();
  const text = ($("chatMessage")?.value || "").trim();
  if (!text) {
    setStatus("Введіть повідомлення", "error");
    return;
  }
  setStatus("Надсилаємо...");
  try {
    const payload = { text };
    await fetchJSON("/chat/user_message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("chatMessage").value = "";
    setStatus("Повідомлення надіслано");
    await loadHistory();
  } catch (err) {
    console.error(err);
    setStatus("Помилка відправлення", "error");
  }
}

function bindEvents() {
  $("chatForm")?.addEventListener("submit", sendMessage);
  pollTimer = setInterval(() => loadHistory(), 2000);
}
bindEvents();
setStatus("Почніть діалог");
