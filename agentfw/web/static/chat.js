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

let conversationId = null;
let pollTimer = null;

function renderMessage(message) {
  const wrapper = document.createElement("div");
  wrapper.className = `chat-row chat-${message.role}`;

  const header = document.createElement("div");
  header.className = "chat-meta";
  header.textContent = message.role === "user" ? "Користувач" : "Агент";
  wrapper.appendChild(header);

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.textContent = message.content || "";
  wrapper.appendChild(bubble);

  if (message.status && message.status !== "ok") {
    const statusLine = document.createElement("div");
    statusLine.className = `chat-status-line status-${message.status}`;
    statusLine.textContent = `Статус: ${message.status}`;
    wrapper.appendChild(statusLine);
  }

  if (message.questions_to_user?.length) {
    const list = document.createElement("ul");
    list.className = "chat-questions";
    message.questions_to_user.forEach((q) => {
      const li = document.createElement("li");
      li.textContent = q;
      list.appendChild(li);
    });
    wrapper.appendChild(list);
  }

  if (message.missing_inputs?.length) {
    const info = document.createElement("div");
    info.className = "chat-missing";
    info.textContent = `Не вистачає: ${message.missing_inputs.join(", ")}`;
    wrapper.appendChild(info);
  }

  if (message.expected_output === "file_written" && message.attachments?.length) {
    const files = document.createElement("div");
    files.className = "chat-files";
    files.textContent = `Файли: ${message.attachments
      .map((a) => a.path || a.name || "файл")
      .join(", ")}`;
    wrapper.appendChild(files);
  }

  return wrapper;
}

function renderHistory(history) {
  const container = $("chatHistory");
  if (!container) return;
  container.innerHTML = "";
  history.forEach((message) => container.appendChild(renderMessage(message)));
  container.scrollTop = container.scrollHeight;
}

async function loadHistory({ usePollEndpoint = false } = {}) {
  if (!conversationId) return;
  try {
    const endpoint = usePollEndpoint
      ? `/api/chat/poll?conversation_id=${encodeURIComponent(conversationId)}`
      : `/api/chat/history?conversation_id=${encodeURIComponent(conversationId)}`;
    const data = await fetchJSON(endpoint);
    renderHistory(data.history || []);
    if (data.status) {
      setChatStatus(`Статус: ${data.status}`);
    }
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити історію", "error");
  }
}

async function sendMessage(event) {
  event?.preventDefault();
  const text = ($("chatMessage")?.value || "").trim();
  const startingConversation = !conversationId;
  if (!text && !startingConversation) {
    setStatus("Введіть повідомлення", "error");
    return;
  }
  setStatus(startingConversation ? "Запитуємо завдання..." : "Надсилаємо...");
  try {
    const payload = {
      message: text || "",
      conversation_id: conversationId,
    };
    const expected = $("expectedOutput")?.value;
    if (expected) payload.expected_output = expected;
    const data = await fetchJSON("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    conversationId = data.conversation_id;
    $("chatMessage").value = "";
    setStatus("Відповідь отримано");
    setChatStatus(`Статус: ${data.status}`);
    await loadHistory();
  } catch (err) {
    console.error(err);
    setStatus("Помилка відправлення", "error");
  }
}

function resetConversation() {
  conversationId = null;
  renderHistory([]);
  setChatStatus("Нова розмова");
  setStatus("Почніть діалог");
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function bindEvents() {
  $("chatForm")?.addEventListener("submit", sendMessage);
  $("newConversationBtn")?.addEventListener("click", resetConversation);
  pollTimer = setInterval(() => loadHistory({ usePollEndpoint: true }), 2000);
}

bindEvents();
setStatus("Почніть діалог");
