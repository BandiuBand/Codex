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
  loadingChildren: false,
};

const CTX_ID = "__CTX__";

let drawBindingsScheduled = false;

function scheduleDrawBindings() {
  if (drawBindingsScheduled) return;
  drawBindingsScheduled = true;
  requestAnimationFrame(() => {
    drawBindingsScheduled = false;
    drawBindings();
  });
}

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

function openRunModal() {
  const modal = $("runModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  renderRunnerSelect();
}

function closeRunModal() {
  const modal = $("runModal");
  if (!modal) return;
  modal.classList.add("hidden");
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
    spec.graph = { lanes: [{ items: [] }, { items: [] }], ctx_bindings: [] };
  }
  if (!Array.isArray(spec.graph.lanes) || !spec.graph.lanes.length) {
    spec.graph.lanes = [{ items: [] }, { items: [] }];
  }
  if (spec.graph.lanes.length < 2) {
    spec.graph.lanes.push({ items: [] });
  }
  if (!Array.isArray(spec.graph.ctx_bindings)) {
    const legacyCtx = spec.graph.__ctx_bindings;
    spec.graph.ctx_bindings = Array.isArray(legacyCtx) ? [...legacyCtx] : [];
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

function collectMissingChildSpecs() {
  if (!state.current?.graph) return [];
  const names = new Set();
  state.current.graph.lanes.forEach((lane) => {
    lane.items.forEach((item) => {
      if (!state.specs[item.agent]) {
        names.add(item.agent);
      }
    });
  });
  return Array.from(names);
}

async function ensureChildSpecsLoaded() {
  const missing = collectMissingChildSpecs();
  if (!missing.length) return;
  try {
    await Promise.all(missing.map((name) => ensureAgentSpec(name)));
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити специфікацію дочірнього агента", "error");
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
    graph: { lanes: [{ items: [] }, { items: [] }], ctx_bindings: [] },
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
    graph: { lanes: [{ items: [] }, { items: [] }], ctx_bindings: [] },
  };
  state.selectedItemId = null;
  state.selectedLane = 0;
  renderCanvas();
}

async function ensureAgentSpec(name) {
  if (state.specs[name]) return state.specs[name];
  const spec = await fetchJSON(`/api/agent/${encodeURIComponent(name)}`);
  if (spec.kind === "composite") ensureGraph(spec);
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

async function renderCanvas() {
  renderAgentVarZones();
  const container = $("lanesContainer");
  const svg = $("bindingsLayer");
  if (container) container.innerHTML = "";
  if (svg) svg.innerHTML = "";
  if (!state.current || !container) return;
  if (!container._scrollBindingAttached) {
    container.addEventListener("scroll", scheduleDrawBindings);
    container._scrollBindingAttached = true;
  }
  ensureGraph(state.current);

  if (!state.loadingChildren) {
    const missing = collectMissingChildSpecs();
    if (missing.length) {
      state.loadingChildren = true;
      await ensureChildSpecsLoaded();
      state.loadingChildren = false;
    }
  }

  state.current.graph.lanes.forEach((lane, laneIndex) => {
    const laneEl = document.createElement("div");
    laneEl.className = `lane ${state.selectedLane === laneIndex ? "lane-active" : ""}`;
    laneEl.dataset.laneIndex = laneIndex;
    laneEl.addEventListener("click", () => {
      state.selectedLane = laneIndex;
      renderCanvas();
    });
    laneEl.addEventListener("dragover", (e) => {
      e.preventDefault();
    });
    laneEl.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!state.cardDrag) return;
      moveCardToLane(state.cardDrag.itemId, state.cardDrag.fromLane, laneIndex);
    });
    laneEl.addEventListener("scroll", scheduleDrawBindings);
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
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "port port-missing";
        placeholder.textContent = "Специфікація завантажується...";
        grid.appendChild(placeholder);
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
  port.addEventListener("mousedown", (e) => {
    if (e.target.closest(".port-actions")) return;
    startDrag(e, itemId, varName, role);
  });
  port.addEventListener("mouseup", (e) => {
    if (e.target.closest(".port-actions")) return;
    finishDrag(e, itemId, varName, role);
  });
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
    state.current.graph.ctx_bindings = (state.current.graph.ctx_bindings || []).filter((b) => b.to_var !== binding.to_var);
    state.current.graph.ctx_bindings.push(binding);
  }
  normalizeLaneOrders();
}

function allBindings() {
  if (!state.current || !state.current.graph) return [];
  const laneBindings = state.current.graph.lanes.flatMap((lane) => lane.items.flatMap((item) => item.bindings || []));
  const ctxBindings = state.current.graph.ctx_bindings || [];
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
  const ctxList = state.current.graph.ctx_bindings || [];
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
  state.current.graph.ctx_bindings = ctxList.filter(
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
  ensureGraph(state.current);
  state.current.inputs.forEach((v) => zones.inputs?.appendChild(makeCtxPort("inputs", v)));
  state.current.locals.forEach((v) => zones.locals?.appendChild(makeCtxPort("locals", v)));
  state.current.outputs.forEach((v) => zones.outputs?.appendChild(makeCtxPort("outputs", v)));
}

function makeCtxPort(kind, variable) {
  const role = kind === "outputs" ? "ctx-output" : kind === "locals" ? "ctx-local" : "ctx-input";
  const port = document.createElement("div");
  port.className = `port port-ctx port-${role}`;
  port.dataset.itemId = CTX_ID;
  port.dataset.varName = variable.name;
  port.dataset.role = role;

  const main = document.createElement("div");
  main.className = "port-main";
  const label = document.createElement("span");
  label.textContent = variable.name;
  main.appendChild(label);
  if (kind === "locals" && variable.value !== undefined) {
    const val = document.createElement("span");
    val.className = "var-value";
    val.textContent = JSON.stringify(variable.value);
    main.appendChild(val);
  }
  port.appendChild(main);

  const actions = document.createElement("div");
  actions.className = "port-actions";
  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = "✎";
  editBtn.className = "ghost tiny";
  editBtn.title = "Редагувати";
  editBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    editAgentVar(kind, variable.name);
  });
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.textContent = "✕";
  removeBtn.className = "ghost tiny";
  removeBtn.title = "Видалити";
  removeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    removeAgentVar(kind, variable.name);
  });
  actions.appendChild(editBtn);
  actions.appendChild(removeBtn);
  port.appendChild(actions);

  port.addEventListener("mousedown", (e) => {
    if (e.target.closest(".port-actions")) return;
    startDrag(e, CTX_ID, variable.name, role);
  });
  port.addEventListener("mouseup", (e) => {
    if (e.target.closest(".port-actions")) return;
    finishDrag(e, CTX_ID, variable.name, role);
  });
  return port;
}

function parseValueInput(raw, fallback) {
  if (raw === null) return fallback;
  const trimmed = String(raw).trim();
  if (!trimmed.length) return "";
  try {
    return JSON.parse(trimmed);
  } catch (err) {
    return trimmed;
  }
}

function editAgentVar(kind, varName) {
  if (!state.current) return;
  const list = state.current[kind];
  const idx = list.findIndex((v) => v.name === varName);
  if (idx === -1) return;
  const current = list[idx];
  const newName = prompt("Нова назва змінної", current.name);
  if (!newName) return;
  let newValue = current.value;
  if (kind === "locals") {
    const defaultVal = current.value === undefined ? "" : JSON.stringify(current.value);
    const rawVal = prompt("Нове значення (JSON дозволено)", defaultVal);
    newValue = parseValueInput(rawVal, current.value);
  }
  if (newName !== varName) {
    renameCtxVarInBindings(varName, newName);
  }
  list[idx] = kind === "locals" ? { name: newName, value: newValue } : { name: newName };
  renderCanvas();
}

function removeAgentVar(kind, varName) {
  if (!state.current) return;
  const list = state.current[kind] || [];
  state.current[kind] = list.filter((v) => v.name !== varName);
  dropBindingsForCtxVar(varName);
  renderCanvas();
}

function dropBindingsForCtxVar(varName) {
  if (!state.current?.graph) return;
  state.current.graph.lanes.forEach((lane) => {
    lane.items.forEach((item) => {
      item.bindings = (item.bindings || []).filter(
        (b) =>
          !(
            (b.from_agent_item_id === CTX_ID && b.from_var === varName) ||
            (b.to_agent_item_id === CTX_ID && b.to_var === varName)
          ),
      );
    });
  });
  state.current.graph.ctx_bindings = (state.current.graph.ctx_bindings || []).filter(
    (b) => b.to_var !== varName && !(b.from_agent_item_id === CTX_ID && b.from_var === varName),
  );
}

function renameCtxVarInBindings(oldName, newName) {
  if (!state.current?.graph) return;
  state.current.graph.lanes.forEach((lane) => {
    lane.items.forEach((item) => {
      item.bindings = (item.bindings || []).map((b) => {
        const copy = { ...b };
        if (copy.from_agent_item_id === CTX_ID && copy.from_var === oldName) copy.from_var = newName;
        if (copy.to_agent_item_id === CTX_ID && copy.to_var === oldName) copy.to_var = newName;
        return copy;
      });
    });
  });
  state.current.graph.ctx_bindings = (state.current.graph.ctx_bindings || []).map((b) => {
    const copy = { ...b };
    if (copy.from_agent_item_id === CTX_ID && copy.from_var === oldName) copy.from_var = newName;
    if (copy.to_agent_item_id === CTX_ID && copy.to_var === oldName) copy.to_var = newName;
    return copy;
  });
}

function addAgentVar(kind) {
  if (!state.current) return;
  const name = prompt(`Нова змінна для ${kind}`);
  if (!name) return;
  if (kind === "inputs") state.current.inputs.push({ name });
  if (kind === "locals") {
    const valueRaw = prompt("Значення за замовчуванням (JSON дозволено)", "");
    state.current.locals.push({ name, value: parseValueInput(valueRaw, "") });
  }
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
  const select = $("runAgentSelect");
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
  $("btnNew")?.addEventListener("click", newAgent);
  $("btnSave")?.addEventListener("click", saveAgent);
  $("btnCreate")?.addEventListener("click", createAgent);
  $("btnAddLane")?.addEventListener("click", addLane);
  $("btnRunOpen")?.addEventListener("click", openRunModal);
  $("runBtn")?.addEventListener("click", runAgent);
  $("runCloseBtn")?.addEventListener("click", closeRunModal);
  $("runModal")?.addEventListener("click", (event) => {
    if (event.target === $("runModal")) closeRunModal();
  });
  document.addEventListener("mouseup", () => {
    state.drag = null;
  });
  setupZoneButtons();
}

window.addEventListener("resize", scheduleDrawBindings);

bindEvents();
loadAgentsList();
newAgent();
