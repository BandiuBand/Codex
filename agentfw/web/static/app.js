/* eslint-disable no-console */
const state = {
  agents: [],
  specs: {},
  current: null,
  selectedItemId: null,
  selectedLane: 0,
  drag: null,
  cardDrag: null,
  counter: 1,
};

const CTX_ID = "__CTX__";

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
    spec.graph = { lanes: [{ items: [] }, { items: [] }] };
  }
  if (!Array.isArray(spec.graph.lanes) || !spec.graph.lanes.length) {
    spec.graph.lanes = [{ items: [] }, { items: [] }];
  }
  if (spec.graph.lanes.length < 2) {
    spec.graph.lanes.push({ items: [] });
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
    graph: { lanes: [{ items: [] }, { items: [] }] },
  };
  state.selectedItemId = null;
  state.selectedLane = 0;
  renderCanvas();
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
    graph: { lanes: [{ items: [] }, { items: [] }] },
  };
  state.selectedItemId = null;
  state.selectedLane = 0;
  renderCanvas();
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
  const laneIndex = state.selectedLane || 0;
  const lane = state.current.graph.lanes[laneIndex] || state.current.graph.lanes[0];
  const itemId = `${agentName}-${Date.now()}-${state.counter++}`;
  lane.items.push({ id: itemId, agent: agentName, bindings: [], ui: { lane_index: laneIndex, order: lane.items.length } });
  state.selectedItemId = itemId;
  await ensureAgentSpec(agentName);
  normalizeLaneOrders();
  renderCanvas();
}

function addLane() {
  if (!state.current) return;
  ensureGraph(state.current);
  state.current.graph.lanes.push({ items: [] });
  state.selectedLane = state.current.graph.lanes.length - 1;
  renderCanvas();
}

function normalizeLaneOrders() {
  if (!state.current?.graph) return;
  state.current.graph.lanes.forEach((lane, laneIndex) => {
    lane.items.forEach((item, idx) => {
      if (!item.ui) item.ui = { lane_index: laneIndex, order: idx };
      item.ui.lane_index = laneIndex;
      item.ui.order = idx;
    });
  });
}

function renderCanvas() {
  renderAgentVarZones();
  const container = $("lanesContainer");
  if (!container) return;
  container.innerHTML = "";
  if (!state.current) return;
  ensureGraph(state.current);
  state.current.graph.lanes.forEach((lane, laneIndex) => {
    const laneEl = document.createElement("div");
    laneEl.className = "lane";
    laneEl.dataset.laneIndex = laneIndex;
    laneEl.addEventListener("click", () => {
      state.selectedLane = laneIndex;
    });
    laneEl.addEventListener("dragover", (e) => {
      e.preventDefault();
    });
    laneEl.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!state.cardDrag) return;
      moveCardToLane(state.cardDrag.itemId, state.cardDrag.fromLane, laneIndex);
    });
    const laneTitle = document.createElement("div");
    laneTitle.className = "lane-title";
    laneTitle.textContent = `Лейн ${laneIndex + 1}`;
    laneEl.appendChild(laneTitle);
    const items = [...lane.items].sort((a, b) => (a.ui?.order || 0) - (b.ui?.order || 0));
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = `agent-card ${state.selectedItemId === item.id ? "selected" : ""}`;
      card.dataset.itemId = item.id;
      card.draggable = true;
      card.addEventListener("dragstart", () => {
        state.cardDrag = { itemId: item.id, fromLane: laneIndex };
      });
      card.addEventListener("dragend", () => {
        state.cardDrag = null;
      });
      card.addEventListener("click", () => {
        state.selectedItemId = item.id;
        renderCanvas();
      });
      const title = document.createElement("div");
      title.className = "agent-title";
      title.textContent = item.agent;
      card.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "card-grid";
      const inputsCol = document.createElement("div");
      inputsCol.className = "inputs-col";
      const outputsCol = document.createElement("div");
      outputsCol.className = "outputs-col";
      const localsRow = document.createElement("div");
      localsRow.className = "locals-row";
      grid.appendChild(inputsCol);
      grid.appendChild(localsRow);
      grid.appendChild(outputsCol);
      card.appendChild(grid);

      const spec = state.specs[item.agent];
      if (spec) {
        spec.inputs.forEach((v) => inputsCol.appendChild(makePort(item.id, v.name, "input")));
        spec.locals.forEach((v) => localsRow.appendChild(makePort(item.id, v.name, "local", v.value)));
        spec.outputs.forEach((v) => outputsCol.appendChild(makePort(item.id, v.name, "output")));
      }

      laneEl.appendChild(card);
    });
    container.appendChild(laneEl);
  });
  drawBindings();
}

function makePort(itemId, varName, role, extraLabel = "") {
  const port = document.createElement("div");
  port.className = `port port-${role}`;
  const label = document.createElement("span");
  label.textContent = varName;
  port.appendChild(label);
  if (extraLabel) {
    const val = document.createElement("span");
    val.className = "var-value";
    val.textContent = extraLabel;
    port.appendChild(val);
  }
  port.dataset.itemId = itemId;
  port.dataset.varName = varName;
  port.dataset.role = role;
  port.addEventListener("mousedown", (e) => startDrag(e, itemId, varName, role));
  port.addEventListener("mouseup", (e) => finishDrag(e, itemId, varName, role));
  return port;
}

function startDrag(event, itemId, varName, role = "ctx") {
  event.stopPropagation();
  state.drag = { fromItem: itemId, fromVar: varName, role };
}

function finishDrag(event, itemId, varName, targetRole) {
  if (!state.drag || !state.current) return;
  event.stopPropagation();
  const source = state.drag;

  // правила: до input дочірнього агента може йти output/local/ctx
  if (targetRole === "input") {
    const allowedSources = ["output", "local", "ctx-input", "ctx-local", "ctx-output"];
    if (!allowedSources.includes(source.role)) {
      state.drag = null;
      return;
    }
    const fromId = source.fromItem;
    const binding = {
      from_agent_item_id: fromId === CTX_ID ? CTX_ID : fromId,
      from_var: source.fromVar,
      to_agent_item_id: itemId,
      to_var: varName,
    };
    addBinding(binding);
    state.drag = null;
    drawBindings();
    return;
  }

  // до ctx-output/local допускаємо підключення з output/local дочірнього
  const targetIsCtxOutput = targetRole === "ctx-output" || targetRole === "ctx-local";
  const sourceIsChild = ["output", "local"].includes(source.role);
  if (targetIsCtxOutput && sourceIsChild) {
    const binding = {
      from_agent_item_id: source.fromItem,
      from_var: source.fromVar,
      to_agent_item_id: CTX_ID,
      to_var: varName,
    };
    addBinding(binding);
    state.drag = null;
    drawBindings();
    return;
  }

  state.drag = null;
}

function addBinding(binding) {
  if (!state.current) return;
  ensureGraph(state.current);
  const allItems = state.current.graph.lanes.flatMap((l) => l.items);
  if (binding.to_agent_item_id !== CTX_ID) {
    const target = allItems.find((i) => i.id === binding.to_agent_item_id);
    if (!target) return;
    target.bindings = (target.bindings || []).filter((b) => b.to_var !== binding.to_var);
    target.bindings.push(binding);
  } else {
    // збережемо окремо у graph __ctx_bindings
    if (!state.current.graph.__ctx_bindings) state.current.graph.__ctx_bindings = [];
    state.current.graph.__ctx_bindings = state.current.graph.__ctx_bindings.filter(
      (b) => !(b.to_var === binding.to_var && b.from_agent_item_id === binding.from_agent_item_id && b.from_var === binding.from_var),
    );
    state.current.graph.__ctx_bindings.push(binding);
  }
  normalizeLaneOrders();
}

function allBindings() {
  if (!state.current || !state.current.graph) return [];
  const laneBindings = state.current.graph.lanes.flatMap((lane) => lane.items.flatMap((item) => item.bindings || []));
  const ctxBindings = state.current.graph.__ctx_bindings || [];
  return [...laneBindings, ...ctxBindings];
}

function drawBindings() {
  const svg = $("bindingsLayer");
  if (!svg) return;
  svg.innerHTML = "";
  const svgRect = svg.getBoundingClientRect();
  const bindings = allBindings();
  bindings.forEach((b) => {
    const fromEl = document.querySelector(`[data-item-id=\"${b.from_agent_item_id}\"][data-var-name=\"${b.from_var}\"]`);
    const toEl = document.querySelector(`[data-item-id=\"${b.to_agent_item_id}\"][data-var-name=\"${b.to_var}\"]`);
    if (!fromEl || !toEl) return;
    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toEl.getBoundingClientRect();
    const startX = fromRect.right - svgRect.left;
    const startY = fromRect.top + fromRect.height / 2 - svgRect.top;
    const endX = toRect.left - svgRect.left;
    const endY = toRect.top + toRect.height / 2 - svgRect.top;
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
  const ctxList = state.current.graph.__ctx_bindings || [];
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
  state.current.graph.__ctx_bindings = ctxList.filter(
    (b) =>
      !(
        b.from_agent_item_id === binding.from_agent_item_id &&
        b.from_var === binding.from_var &&
        b.to_agent_item_id === binding.to_agent_item_id &&
        b.to_var === binding.to_var
      ),
  );
  drawBindings();
}

function moveCardToLane(itemId, fromLaneIdx, toLaneIdx) {
  if (!state.current?.graph) return;
  if (fromLaneIdx === toLaneIdx) return;
  const fromLane = state.current.graph.lanes[fromLaneIdx];
  const toLane = state.current.graph.lanes[toLaneIdx];
  if (!fromLane || !toLane) return;
  const idx = fromLane.items.findIndex((i) => i.id === itemId);
  if (idx === -1) return;
  const [item] = fromLane.items.splice(idx, 1);
  if (!item.ui) item.ui = { lane_index: toLaneIdx, order: toLane.items.length };
  item.ui.lane_index = toLaneIdx;
  item.ui.order = toLane.items.length;
  toLane.items.push(item);
  normalizeLaneOrders();
  renderCanvas();
}

function renderAgentVarZones() {
  const zones = {
    inputs: $("canvasInputs"),
    locals: $("canvasLocals"),
    outputs: $("canvasOutputs"),
  };
  Object.values(zones).forEach((el) => {
    if (el) el.innerHTML = "";
  });
  if (!state.current) return;
  state.current.inputs.forEach((v) => zones.inputs?.appendChild(makePort(CTX_ID, v.name, "ctx-input")));
  state.current.locals.forEach((v) => zones.locals?.appendChild(makePort(CTX_ID, v.name, "ctx-local", v.value)));
  state.current.outputs.forEach((v) => zones.outputs?.appendChild(makePort(CTX_ID, v.name, "ctx-output")));
}

function addAgentVar(kind) {
  if (!state.current) return;
  const name = prompt(`Нова змінна для ${kind}`);
  if (!name) return;
  if (kind === "inputs") state.current.inputs.push({ name });
  if (kind === "locals") state.current.locals.push({ name, value: "" });
  if (kind === "outputs") state.current.outputs.push({ name });
  renderCanvas();
}

function setupZoneButtons() {
  document.querySelectorAll(".zone-add").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const kind = e.target.dataset.kind;
      addAgentVar(kind);
    });
  });
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
  $("btnAddLane")?.addEventListener("click", addLane);
  $("runBtn")?.addEventListener("click", runAgent);
  document.addEventListener("mouseup", () => {
    state.drag = null;
  });
  setupZoneButtons();
}

window.addEventListener("resize", drawBindings);

bindEvents();
loadAgentsList();
newAgent();
