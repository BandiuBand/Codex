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

async function fetchJSON(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function loadAgents() {
  try {
    const data = await fetchJSON("/api/agents");
    const select = $("runAgentSelect");
    if (!select) return;
    select.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "— оберіть агента —";
    select.appendChild(placeholder);
    (Array.isArray(data) ? data : []).forEach((agent) => {
      const opt = document.createElement("option");
      opt.value = agent.name;
      opt.textContent = agent.title_ua || agent.name;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити список агентів", "error");
  }
}

async function runAgent() {
  const select = $("runAgentSelect");
  if (!select) return;
  const name = select.value;
  if (!name) return setStatus("Оберіть агента для запуску", "error");
  let inputPayload = {};
  try {
    inputPayload = JSON.parse($("runInputField").value || "{}");
  } catch (err) {
    return setStatus("Некоректний JSON", "error");
  }
  try {
    const result = await fetchJSON(`/api/run/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: inputPayload }),
    });
    $("runOutputField").value = JSON.stringify(result, null, 2);
    setStatus("Агент виконано");
  } catch (err) {
    console.error(err);
    setStatus("Помилка виконання", "error");
  }
}

function bindEvents() {
  $("runBtn")?.addEventListener("click", runAgent);
}

bindEvents();
loadAgents();
