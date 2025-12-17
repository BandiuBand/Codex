/* eslint-disable no-console */
const state = {
  agents: [],
  specs: {},
  current: null,
  selectedItemId: null,
  drag: null,
  counter: 1,
};

const ctxSource = { id: "__CTX__", label: "CTX" };

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

function ensureGraph(spec) {
  if (!spec.graph) {
    spec.graph = { lanes: [{ items: [] }] };
  }
  if (!Array.isArray(spec.graph.lanes) || !spec.graph.lanes.length) {
    spec.graph.lanes = [{ items: [] }];
  }
}

async function loadAgentsList() {
  try {
    const data = await fetchJSON("/api/agents");
    state.agents = Array.isArray(data) ? data : [];
    renderMenus();
    renderRunnerSelect();
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити список агентів", "error");
  }
}

function renderMenus() {
  const loadMenu = $("loadMenu");
  const addMenu = $("addMenu");
  [loadMenu, addMenu].forEach((menu) => {
    if (menu) menu.innerHTML = "";
  });

  state.agents.forEach((agent) => {
    const item = document.createElement("div");
    item.textContent = agent.title_ua || agent.name;
    item.addEventListener("click", () => openAgent(agent.name));
    loadMenu?.appendChild(item);

    const addItem = document.createElement("div");
    addItem.textContent = agent.title_ua || agent.name;
    addItem.addEventListener("click", () => insertAgentItem(agent.name));
    addMenu?.appendChild(addItem);
  });
}

async function openAgent(name) {
  try {
    const spec = await fetchJSON(`/api/agent/${encodeURIComponent(name)}`);
    ensureGraph(spec);
    state.specs[spec.name] = spec;
    state.current = spec;
    state.selectedItemId = null;
    state.counter = 1;
    renderCanvas();
    renderInspector();
    setStatus(`Відкрито агента ${spec.title_ua || spec.name}`);
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити агента", "error");
  }
}

function newAgent() {
  state.current = {
    name: "новий",
    title_ua: "Новий агент",
    description_ua: "",
    kind: "composite",
    inputs: [],
    locals: [],
    outputs: [],
    graph: { lanes: [{ items: [] }] },
  };
  state.selectedItemId = null;
  renderCanvas();
  renderInspector();
}

async function saveAgent() {
  if (!state.current) return;
  try {
    await fetchJSON(`/api/agent/${encodeURIComponent(state.current.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.current),
    });
    setStatus("Збережено");
    await loadAgentsList();
  } catch (err) {
    console.error(err);
    setStatus("Помилка збереження", "error");
  }
}

function createAgent() {
  const name = prompt("Назва нового агента");
  if (!name) return;
  state.current = {
    name,
    title_ua: name,
    description_ua: "",
    kind: "composite",
    inputs: [],
    locals: [],
    outputs: [],
    graph: { lanes: [{ items: [] }] },
  };
  state.selectedItemId = null;
  renderCanvas();
  renderInspector();
}

function findAgentSpec(name) {
  return state.specs[name] || null;
}

async function ensureAgentSpec(name) {
  if (state.specs[name]) return state.specs[name];
  const spec = await fetchJSON(`/api/agent/${encodeURIComponent(name)}`);
  state.specs[name] = spec;
  return spec;
}

async function insertAgentItem(agentName) {
  if (!state.current) return;
  ensureGraph(state.current);
  const lane = state.current.graph.lanes[0];
  const itemId = `${agentName}-${Date.now()}-${state.counter++}`;
  lane.items.push({ id: itemId, agent: agentName, bindings: [], ui: { lane_index: 0, order: lane.items.length } });
  state.selectedItemId = itemId;
  await ensureAgentSpec(agentName);
  renderCanvas();
  renderInspector();
}

function renderCanvas() {
  const container = $("lanesContainer");
  if (!container) return;
  container.innerHTML = "";
  if (!state.current) return;
  ensureGraph(state.current);
  state.current.graph.lanes.forEach((lane, laneIndex) => {
    const laneEl = document.createElement("div");
    laneEl.className = "lane";
    const laneTitle = document.createElement("div");
    laneTitle.className = "lane-title";
    laneTitle.textContent = `Лейн ${laneIndex + 1}`;
    laneEl.appendChild(laneTitle);
    const items = [...lane.items].sort((a, b) => (a.ui?.order || 0) - (b.ui?.order || 0));
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = `agent-card ${state.selectedItemId === item.id ? "selected" : ""}`;
      card.dataset.itemId = item.id;
      card.addEventListener("click", () => {
        state.selectedItemId = item.id;
        renderInspector();
        renderCanvas();
      });
      const title = document.createElement("div");
      title.className = "agent-title";
      title.textContent = item.agent;
      card.appendChild(title);

      const inputsRow = document.createElement("div");
      inputsRow.className = "ports inputs";
      const outputsRow = document.createElement("div");
      outputsRow.className = "ports outputs";
      const localsRow = document.createElement("div");
      localsRow.className = "ports locals";
      card.appendChild(inputsRow);
      card.appendChild(localsRow);
      card.appendChild(outputsRow);

      const spec = state.specs[item.agent];
      if (spec) {
        spec.inputs.forEach((v) => inputsRow.appendChild(makePort(item.id, v.name, "input")));
        spec.locals.forEach((v) => localsRow.appendChild(makePort(item.id, v.name, "local")));
        spec.outputs.forEach((v) => outputsRow.appendChild(makePort(item.id, v.name, "output")));
      }

      laneEl.appendChild(card);
    });
    container.appendChild(laneEl);
  });
  drawBindings();
}

function makePort(itemId, varName, role) {
  const port = document.createElement("div");
  port.className = `port port-${role}`;
  port.textContent = varName;
  port.dataset.itemId = itemId;
  port.dataset.varName = varName;
  port.dataset.role = role;
  port.addEventListener("mousedown", (e) => startDrag(e, itemId, varName));
  port.addEventListener("mouseup", (e) => finishDrag(e, itemId, varName));
  return port;
}

function startDrag(event, itemId, varName) {
  event.stopPropagation();
  state.drag = { fromItem: itemId, fromVar: varName };
}

function finishDrag(event, itemId, varName) {
  if (!state.drag || !state.current) return;
  event.stopPropagation();
  const binding = {
    from_agent_item_id: state.drag.fromItem,
    from_var: state.drag.fromVar,
    to_agent_item_id: itemId,
    to_var: varName,
  };
  addBinding(binding);
  state.drag = null;
  drawBindings();
}

function addBinding(binding) {
  if (!state.current) return;
  ensureGraph(state.current);
  const allItems = state.current.graph.lanes.flatMap((l) => l.items);
  const target = allItems.find((i) => i.id === binding.to_agent_item_id);
  if (!target) return;
  target.bindings = (target.bindings || []).filter((b) => b.to_var !== binding.to_var);
  target.bindings.push(binding);
}

function allBindings() {
  if (!state.current || !state.current.graph) return [];
  return state.current.graph.lanes.flatMap((lane) => lane.items.flatMap((item) => item.bindings || []));
}

function drawBindings() {
  const svg = $("bindingsLayer");
  if (!svg) return;
  svg.innerHTML = "";
  const bindings = allBindings();
  bindings.forEach((b) => {
    const fromEl = document.querySelector(`[data-item-id="${b.from_agent_item_id}"][data-var-name="${b.from_var}"]`);
    const toEl = document.querySelector(`[data-item-id="${b.to_agent_item_id}"][data-var-name="${b.to_var}"]`);
    if (!fromEl || !toEl) return;
    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toEl.getBoundingClientRect();
    const startX = fromRect.right;
    const startY = fromRect.top + fromRect.height / 2;
    const endX = toRect.left;
    const endY = toRect.top + toRect.height / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const d = `M ${startX} ${startY} C ${startX + 50} ${startY} ${endX - 50} ${endY} ${endX} ${endY}`;
    path.setAttribute("d", d);
    path.setAttribute("class", "binding-line");
    path.addEventListener("click", () => {
      removeBinding(b);
    });
    svg.appendChild(path);
  });
}

function removeBinding(binding) {
  if (!state.current) return;
  state.current.graph.lanes.forEach((lane) => {
    lane.items.forEach((item) => {
      item.bindings = (item.bindings || []).filter(
        (b) =>
          !(
            b.from_agent_item_id === binding.from_agent_item_id &&
            b.from_var === binding.from_var &&
            b.to_agent_item_id === binding.to_agent_item_id &&
            b.to_var === binding.to_var
          ),
      );
    });
  });
  drawBindings();
}

function renderInspector() {
  const panels = {
    inputs: $("inputsPanel"),
    locals: $("localsPanel"),
    outputs: $("outputsPanel"),
  };
  Object.values(panels).forEach((panel) => {
    if (panel) panel.innerHTML = "";
  });
  if (!state.current || !state.selectedItemId) return;
  const allItems = state.current.graph.lanes.flatMap((l) => l.items);
  const item = allItems.find((i) => i.id === state.selectedItemId);
  if (!item) return;
  const spec = state.specs[item.agent];
  if (!spec) return;
  spec.inputs.forEach((v) => renderVarRow(panels.inputs, v.name));
  spec.locals.forEach((v) => renderVarRow(panels.locals, v.name, v.value));
  spec.outputs.forEach((v) => renderVarRow(panels.outputs, v.name));
}

function renderVarRow(container, name, value = "") {
  if (!container) return;
  const row = document.createElement("div");
  row.className = "var-row";
  const handle = document.createElement("span");
  handle.className = "var-handle";
  handle.dataset.itemId = ctxSource.id;
  handle.dataset.varName = name;
  handle.addEventListener("mousedown", (e) => startDrag(e, ctxSource.id, name));
  row.appendChild(handle);
  const badge = document.createElement("span");
  badge.className = "var-badge";
  badge.textContent = name;
  row.appendChild(badge);
  if (value) {
    const val = document.createElement("span");
    val.className = "var-value";
    val.textContent = value;
    row.appendChild(val);
  }
  container.appendChild(row);
}

function renderRunnerSelect() {
  const select = $("runAgent");
  if (!select) return;
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "— оберіть агента —";
  select.appendChild(placeholder);
  state.agents.forEach((agent) => {
    const opt = document.createElement("option");
    opt.value = agent.name;
    opt.textContent = agent.title_ua || agent.name;
    select.appendChild(opt);
  });
}

async function runAgent() {
  const select = $("runAgent");
  if (!select) return;
  const name = select.value;
  if (!name) return setStatus("Оберіть агента для запуску", "error");
  let inputPayload = {};
  try {
    inputPayload = JSON.parse($("runInput").value || "{}");
  } catch (err) {
    return setStatus("Некоректний JSON", "error");
  }
  try {
    const result = await fetchJSON(`/api/run/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: inputPayload }),
    });
    $("runOutput").value = JSON.stringify(result, null, 2);
    setStatus("Агент виконано");
  } catch (err) {
    console.error(err);
    setStatus("Помилка виконання", "error");
  }
}

function bindEvents() {
  $("btnNew")?.addEventListener("click", newAgent);
  $("btnSave")?.addEventListener("click", saveAgent);
  $("btnCreate")?.addEventListener("click", createAgent);
  $("runBtn")?.addEventListener("click", runAgent);
  document.addEventListener("mouseup", () => {
    state.drag = null;
  });
}

window.addEventListener("resize", drawBindings);

bindEvents();
loadAgentsList();
newAgent();
