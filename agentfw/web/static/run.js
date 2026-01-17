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

function setHint(message) {
  const el = $("runHint");
  if (!el) return;
  el.textContent = message || "";
  el.hidden = !message;
}

function updateHint(agentName) {
  if (agentName === "adaptive_task_agent") {
    setHint("Для adaptive_task_agent вкажіть текстове завдання (task або user_message) або скористайтеся сторінкою чату.");
    return;
  }
  setHint("");
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
    updateHint(select.value);
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
    const agentLabel = result?.agent || name;
    setStatus(`Агент ${agentLabel} виконано`);
  } catch (err) {
    console.error(err);
    setStatus(err?.message || "Помилка виконання", "error");
  }
}

function bindEvents() {
  $("runBtn")?.addEventListener("click", runAgent);
  $("runAgentSelect")?.addEventListener("change", (event) => {
    updateHint(event.target?.value || "");
  });
}

bindEvents();
loadAgents();
