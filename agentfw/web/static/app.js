/* eslint-disable no-console */
const state = {
  agents: [],
  specs: {},
  current: null,
  selectedItemId: null,
  selectedLane: 0,
  drag: null,
  cardDrag: null,
  canvasScale: 1,
  counter: 1,
  loadingChildren: false,
  laneWidths: [],
};

const CTX_ID = "__CTX__";
const DEFAULT_LANE_WIDTH = 340;
const DEFAULT_ZONE_WIDTH = 200;
const DEFAULT_GAP = 12;
const STOP_AGENT_INPUT = "stop_agent_execution";

function createStopAgentInput() {
  return { name: STOP_AGENT_INPUT, type: "bool", default: false };
}

function cssNumber(varName, fallback) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName);
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

let drawBindingsScheduled = false;

function syncTopbarHeight() {
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;
  const height = topbar.getBoundingClientRect().height;
  document.documentElement.style.setProperty("--topbar-height", `${height}px`);
}

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

function getNameInput() {
  return $("agentNameInput");
}

function syncNameInput() {
  const input = getNameInput();
  if (!input) return;
  const value = state.current?.name || "";
  input.value = value;
  const isValid = Boolean(value.trim());
  input.classList.toggle("input-error", !isValid);
  input.setCustomValidity(isValid ? "" : "Назва не може бути порожньою");
}

function applyNameFromInput(showErrors = false) {
  const input = getNameInput();
  if (!input || !state.current) return false;
  const trimmed = input.value.trim();
  if (!trimmed) {
    input.classList.add("input-error");
    input.setCustomValidity("Назва не може бути порожньою");
    if (showErrors) {
      input.reportValidity?.();
      setStatus("Назва агента не може бути порожньою", "error");
    }
    return false;
  }

  const prevName = state.current.name;
  state.current.name = trimmed;
  if (!state.current.title_ua || state.current.title_ua === prevName) {
    state.current.title_ua = trimmed;
  }

  if (prevName && prevName !== trimmed) {
    if (state.specs[prevName]) {
      state.specs[trimmed] = state.specs[prevName];
      delete state.specs[prevName];
    }
    const idx = state.agents.findIndex((agent) => agent.name === prevName);
    if (idx !== -1) {
      state.agents[idx] = { ...state.agents[idx], name: trimmed, title_ua: state.current.title_ua || trimmed };
      renderMenus();
    }
  }

  input.value = trimmed;
  input.classList.remove("input-error");
  input.setCustomValidity("");
  return true;
}

function openRunModal() {
  const modal = $("runModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  renderRunnerSelect();
}

function closeRunModal() {
  const modal = $("runModal");
  if (!modal) return;
  modal.classList.add("hidden");
  document.body.classList.remove("modal-open");
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

function getAgentDisplayName(agentName) {
  const spec = state.specs?.[agentName];
  if (spec?.title_ua || spec?.name) {
    return spec.title_ua || spec.name;
  }

  const listAgent = state.agents?.find((agent) => agent.name === agentName);
  if (listAgent?.title_ua || listAgent?.name) {
    return listAgent.title_ua || listAgent.name;
  }

  return agentName;
}

function getItemLaneIndex(itemId) {
  if (!state.current?.graph) return null;
  if (itemId === CTX_ID) return null;
  for (let laneIndex = 0; laneIndex < state.current.graph.lanes.length; laneIndex += 1) {
    const lane = state.current.graph.lanes[laneIndex];
    const item = lane.items.find((i) => i.id === itemId);
    if (item) {
      if (item.ui) item.ui.lane_index = laneIndex;
      return laneIndex;
    }
  }
  return null;
}

function getItemById(itemId) {
  if (!state.current?.graph || itemId === CTX_ID) return null;
  for (const lane of state.current.graph.lanes) {
    const item = lane.items.find((i) => i.id === itemId);
    if (item) return item;
  }
  return null;
}

function isMultiInputPort(itemId, varName, role) {
  if (role !== "input") return false;
  const item = getItemById(itemId);
  if (!item) return false;
  return item.agent === "json_list_pack" && varName === "елементи";
}

async function loadAgentsList() {
  try {
    const data = await fetchJSON("/api/agents");
    state.agents = Array.isArray(data) ? data : [];
    renderMenus();
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
    syncNameInput();
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
    inputs: [createStopAgentInput()],
    locals: [],
    outputs: [],
    graph: { lanes: [{ items: [] }, { items: [] }], ctx_bindings: [] },
  };
  state.selectedItemId = null;
  state.selectedLane = 0;
  syncNameInput();
  renderCanvas();
}

async function saveAgent() {
  if (!state.current) return;
  if (!applyNameFromInput(true)) return;
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
    inputs: [createStopAgentInput()],
    locals: [],
    outputs: [],
    graph: { lanes: [{ items: [] }, { items: [] }], ctx_bindings: [] },
  };
  state.selectedItemId = null;
  state.selectedLane = 0;
  syncNameInput();
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

function hasBindingsForItem(itemId) {
  return allBindings().some((b) => b.from_agent_item_id === itemId || b.to_agent_item_id === itemId);
}

function removeAgentItem(itemId, laneIndex = null) {
  if (!state.current?.graph) return;
  const resolvedLaneIndex =
    Number.isInteger(laneIndex) && laneIndex >= 0 ? laneIndex : getItemLaneIndex(itemId);
  if (resolvedLaneIndex === null || resolvedLaneIndex === undefined) return;
  const lane = state.current.graph.lanes[resolvedLaneIndex];
  if (!lane) return;
  const idx = lane.items.findIndex((i) => i.id === itemId);
  if (idx === -1) return;

  const item = lane.items[idx];
  const label = item?.agent ? `агента ${item.agent}` : "цей елемент";
  const needsConfirm = hasBindingsForItem(itemId);
  if (needsConfirm && !confirm(`Видалити ${label}?`)) return;

  lane.items.splice(idx, 1);
  dropBindingsForItem(itemId);
  if (state.selectedItemId === itemId) {
    state.selectedItemId = null;
  }
  normalizeLaneOrders();
  renderCanvas();
}

function addLane(insertPosition = null) {
  if (!state.current) return;
  ensureGraph(state.current);
  const lanes = state.current.graph.lanes;
  const position = Number.isInteger(insertPosition)
    ? Math.min(Math.max(insertPosition, 0), lanes.length)
    : lanes.length;
  lanes.splice(position, 0, { items: [] });
  state.selectedLane = position;
  normalizeLaneOrders();
  renderCanvas();
}

function addLaneAfterActive() {
  const insertAfter = (state.selectedLane ?? -1) + 1;
  addLane(insertAfter);
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
  const viewport = $("canvasViewport");
  const content = $("canvasContent");
  const scaled = $("canvasScaled");
  const laneScrollOffsets = new Map();
  if (container) {
    container.querySelectorAll(".lane").forEach((laneEl) => {
      const idx = Number.parseInt(laneEl.dataset.laneIndex, 10);
      if (!Number.isNaN(idx)) {
        laneScrollOffsets.set(idx, laneEl.scrollTop);
      }
    });
  }
  const viewportScroll = viewport
    ? { top: viewport.scrollTop, left: viewport.scrollLeft }
    : null;
  if (container) container.innerHTML = "";
  if (svg) svg.innerHTML = "";
  if (!state.current || !container || !viewport) return;
  syncNameInput();
  if (scaled) {
    scaled.style.width = "";
    scaled.style.height = "";
  }
  if (!viewport._scrollBindingAttached) {
    viewport.addEventListener("scroll", scheduleDrawBindings);
    viewport._scrollBindingAttached = true;
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

  const leftZone = viewport.querySelector(".var-zone-left");
  const rightZone = viewport.querySelector(".var-zone-right");
  const topZone = viewport.querySelector(".var-zone-top");
  const leftOffset = leftZone?.offsetWidth || 0;
  const rightOffset = rightZone?.offsetWidth || 0;
  const topOffset = topZone?.offsetHeight || 0;
  canvasContent.style.setProperty("--canvas-left-offset", `${leftOffset}px`);
  canvasContent.style.setProperty("--canvas-right-offset", `${rightOffset}px`);
  canvasContent.style.setProperty("--canvas-top-offset", `${topOffset}px`);

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
      const dropIndex = findDropIndex(laneEl, e.clientY, state.cardDrag.itemId);
      moveCardToLane(state.cardDrag.itemId, state.cardDrag.fromLane, laneIndex, dropIndex);
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
      card.draggable = false;
      card.addEventListener("click", () => {
        state.selectedItemId = item.id;
        renderCanvas();
      });

      const controls = document.createElement("div");
      controls.className = "card-controls";

      const dragHandle = document.createElement("div");
      dragHandle.className = "card-drag-handle";
      dragHandle.title = "Перетягнути агента";
      dragHandle.draggable = true;
      dragHandle.addEventListener("mousedown", (event) => {
        event.stopPropagation();
      });
      dragHandle.addEventListener("dragstart", (event) => {
        if (state.draggingPort) {
          event.preventDefault();
          return;
        }
        state.cardDrag = { itemId: item.id, fromLane: laneIndex };
      });
      dragHandle.addEventListener("dragend", () => {
        state.cardDrag = null;
        card.draggable = true;
      });
      controls.appendChild(dragHandle);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "✕";
      removeBtn.className = "ghost tiny card-remove";
      removeBtn.title = "Видалити агента";
      removeBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        removeAgentItem(item.id, laneIndex);
      });
      controls.appendChild(removeBtn);

      card.appendChild(controls);

      const title = document.createElement("div");
      title.className = "agent-title";
      title.textContent = getAgentDisplayName(item.agent);
      card.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "card-grid";
      const inputsCol = document.createElement("div");
      inputsCol.className = "inputs-col";
      const outputsCol = document.createElement("div");
      outputsCol.className = "outputs-col";
      grid.appendChild(inputsCol);
      grid.appendChild(outputsCol);
      card.appendChild(grid);

      const spec = state.specs[item.agent];
      if (spec) {
        spec.inputs.forEach((v) => inputsCol.appendChild(makePort(item.id, v.name, "input")));
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

  requestAnimationFrame(() => {
    laneScrollOffsets.forEach((scrollTop, laneIndex) => {
      const laneEl = container.querySelector(`.lane[data-lane-index="${laneIndex}"]`);
      if (laneEl) laneEl.scrollTop = scrollTop;
    });
    if (viewportScroll) {
      viewport.scrollTop = viewportScroll.top;
      viewport.scrollLeft = viewportScroll.left;
    }
    state.laneWidths = measureLaneWidths();
    applyCanvasScale();
    drawBindings();
  });
}

function measureLaneWidths() {
  const lanesContainer = $("lanesContainer");
  const canvasContent = $("canvasContent");
  if (!lanesContainer) return [];
  const previousScale = canvasContent?.style.getPropertyValue("--canvas-scale");
  if (canvasContent) {
    canvasContent.style.setProperty("--canvas-scale", 1);
  }
  const fallbackWidth = cssNumber("--lane-width", DEFAULT_LANE_WIDTH);
  const laneWidths = [];

  lanesContainer.querySelectorAll(".lane").forEach((laneEl) => {
    const getWidestPort = (ports) => {
      const widths = ports
        .map((port) => port.offsetWidth || port.clientWidth || 0)
        .sort((a, b) => b - a);
      return widths[0] || 0;
    };

    const measureCardWidth = (cardEl) => {
      const inputPorts = Array.from(cardEl.querySelectorAll(".inputs-col .port"));
      const outputPorts = Array.from(cardEl.querySelectorAll(".outputs-col .port"));
      const widestInput = getWidestPort(inputPorts);
      const widestOutput = getWidestPort(outputPorts);
      const cardPadding = 16; // padding-left + padding-right on .agent-card
      const gridPadding = 32; // padding-left + padding-right on .card-grid
      const columnGap = 16; // horizontal gap between grid columns
      const width = widestInput + widestOutput + columnGap + cardPadding + gridPadding + 4;

      if (width > 0) {
        cardEl.style.minWidth = `${width}px`;
        cardEl.style.width = `${width}px`;
        cardEl.dataset.cardWidth = width;
      } else {
        cardEl.style.minWidth = "";
        cardEl.style.width = "";
        delete cardEl.dataset.cardWidth;
      }

      return width;
    };

    const cards = Array.from(laneEl.querySelectorAll(".agent-card"));
    const widestCard = cards.reduce((max, card) => Math.max(max, measureCardWidth(card)), 0);
    const laneStyle = getComputedStyle(laneEl);
    const horizontalPadding =
      (Number.parseFloat(laneStyle.paddingLeft) || 0) + (Number.parseFloat(laneStyle.paddingRight) || 0);
    const laneWidth = widestCard > 0 ? widestCard + horizontalPadding : fallbackWidth;
    laneEl.style.width = `${laneWidth}px`;
    laneEl.style.minWidth = `${laneWidth}px`;
    laneWidths.push(laneWidth);
  });

  if (laneWidths.length) {
    lanesContainer.style.gridTemplateColumns = laneWidths.map((w) => `${w}px`).join(" ");
  } else {
    lanesContainer.style.gridTemplateColumns = "";
  }

  if (canvasContent && previousScale) {
    canvasContent.style.setProperty("--canvas-scale", previousScale);
  }

  return laneWidths;
}

function applyCanvasScale() {
  const content = $("canvasContent");
  const scaled = $("canvasScaled");
  const viewport = $("canvasViewport");
  const lanesEl = $("lanesContainer");
  if (!content || !scaled || !viewport) return;
  const scale = state.canvasScale || 1;
  const zoneWidth = cssNumber("--zone-width", DEFAULT_ZONE_WIDTH);
  const gap = cssNumber("--canvas-gap", DEFAULT_GAP);
  const laneCount = Math.max(state.current?.graph?.lanes?.length || 0, 1);
  const measuredLaneWidths = state.laneWidths || [];
  const defaultLaneWidth = cssNumber("--lane-width", DEFAULT_LANE_WIDTH);
  const laneWidths = Array.from({ length: laneCount }, (_, idx) => measuredLaneWidths[idx] ?? defaultLaneWidth);
  const lanesWidth = laneWidths.reduce((sum, width) => sum + width, 0);
  const baseWidth = lanesWidth + zoneWidth * 2 + gap * 2;
  const laneHeight = lanesEl ? lanesEl.scrollHeight : 0;
  const baseHeight = Math.max(laneHeight, content.scrollHeight, viewport.clientHeight);

  content.style.width = `${baseWidth}px`;
  content.style.height = `${baseHeight}px`;
  content.style.setProperty("--canvas-scale", scale);
  scaled.style.width = `${baseWidth * scale}px`;
  scaled.style.height = `${baseHeight * scale}px`;
}

function makePort(itemId, varName, role, extraLabel = "") {
  const port = document.createElement("div");
  port.className = `port port-${role}`;
  const icon = document.createElement("span");
  icon.className = "port-icon";
  port.appendChild(icon);
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

  if (isMultiInputPort(itemId, varName, role)) {
    port.classList.add("port-multi");
    port.title = "Порт приймає кілька підключень";
  }

  if (role === "local") {
    port.classList.add("port-disabled");
    port.title = "Зовнішні зв'язки для локальних портів недоступні";
    return port;
  }

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
  event.preventDefault();
  event.stopPropagation();
  event.preventDefault();
  state.draggingPort = true;
  state.drag = { fromItem: itemId, fromVar: varName, role };
}

function finishDrag(event, itemId, varName, targetRole) {
  if (!state.drag || !state.current) return;
  event.stopPropagation();
  normalizeLaneOrders();
  const source = state.drag;
  const clearDrag = () => {
    state.drag = null;
    state.draggingPort = false;
  };

  // правила: до input дочірнього агента може йти output/ctx
  if (targetRole === "input") {
    const allowedSources = ["output", "ctx-input", "ctx-local", "ctx-output"];
    if (!allowedSources.includes(source.role)) {
      clearDrag();
      return;
    }
    const sourceLane = getItemLaneIndex(source.fromItem);
    const targetLane = getItemLaneIndex(itemId);
    if (sourceLane !== null && targetLane !== null && sourceLane === targetLane) {
      setStatus("Не можна створити зв'язок між елементами в одному lane", "warn");
      clearDrag();
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
    clearDrag();
    drawBindings();
    return;
  }

  // до ctx-output/local допускаємо підключення лише з output дочірнього
  const targetIsCtxOutput = targetRole === "ctx-output" || targetRole === "ctx-local";
  const sourceIsChild = ["output"].includes(source.role);
  if (targetIsCtxOutput && sourceIsChild) {
    const sourceLane = getItemLaneIndex(source.fromItem);
    const targetLane = getItemLaneIndex(CTX_ID);
    if (sourceLane !== null && targetLane !== null && sourceLane === targetLane) {
      setStatus("Не можна створити зв'язок між елементами в одному lane", "warn");
      clearDrag();
      return;
    }
    const binding = {
      from_agent_item_id: source.fromItem,
      from_var: source.fromVar,
      to_agent_item_id: CTX_ID,
      to_var: varName,
    };
    addBinding(binding);
    clearDrag();
    drawBindings();
    return;
  }

  clearDrag();
}

function addBinding(binding) {
  if (!state.current) return;
  ensureGraph(state.current);
  normalizeLaneOrders();
  const sourceLane = getItemLaneIndex(binding.from_agent_item_id);
  const targetLane = getItemLaneIndex(binding.to_agent_item_id);
  if (sourceLane !== null && targetLane !== null && sourceLane === targetLane) {
    setStatus("Не можна створити зв'язок між елементами в одному lane", "warn");
    return;
  }
  const allItems = state.current.graph.lanes.flatMap((l) => l.items);
  if (binding.to_agent_item_id !== CTX_ID) {
    const target = allItems.find((i) => i.id === binding.to_agent_item_id);
    if (!target) return;
    const allowsMultiple = isMultiInputPort(binding.to_agent_item_id, binding.to_var, "input");
    if (allowsMultiple) {
      target.bindings = (target.bindings || []).filter(
        (b) =>
          !(
            b.from_agent_item_id === binding.from_agent_item_id &&
            b.from_var === binding.from_var &&
            b.to_var === binding.to_var
          )
      );
      target.bindings.push(binding);
    } else {
      target.bindings = (target.bindings || []).filter((b) => b.to_var !== binding.to_var);
      target.bindings.push(binding);
    }
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
  const canvasContent = $("canvasContent");
  if (!svg || !canvasContent) return;
  svg.innerHTML = "";
  const contentRect = canvasContent.getBoundingClientRect();
  svg.setAttribute("width", `${contentRect.width}`);
  svg.setAttribute("height", `${contentRect.height}`);
  svg.setAttribute("viewBox", `0 0 ${contentRect.width} ${contentRect.height}`);
  const bindings = allBindings();
  bindings.forEach((b) => {
    const fromEl = document.querySelector(`[data-item-id=\"${b.from_agent_item_id}\"][data-var-name=\"${b.from_var}\"]`);
    const toEl = document.querySelector(`[data-item-id=\"${b.to_agent_item_id}\"][data-var-name=\"${b.to_var}\"]`);
    if (!fromEl || !toEl) return;
    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toEl.getBoundingClientRect();
    const startX = fromRect.right - contentRect.left;
    const startY = fromRect.top + fromRect.height / 2 - contentRect.top;
    const endX = toRect.left - contentRect.left;
    const endY = toRect.top + toRect.height / 2 - contentRect.top;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const d = `M ${startX} ${startY} C ${startX + 50} ${startY} ${endX - 50} ${endY} ${endX} ${endY}`;
    path.setAttribute("d", d);
    path.setAttribute("class", "binding-line");
    path.style.stroke = bindingColor(b);
    path.addEventListener("click", () => {
      removeBinding(b);
    });
    svg.appendChild(path);
  });
}

function bindingColor(binding) {
  if (!state.current) return "#58a6ff";
  const kindOfCtxVar = (varName) => {
    if (state.current.inputs?.some((v) => v.name === varName)) return "inputs";
    if (state.current.locals?.some((v) => v.name === varName)) return "locals";
    if (state.current.outputs?.some((v) => v.name === varName)) return "outputs";
    return null;
  };

  const sourceKind = binding.from_agent_item_id === CTX_ID ? kindOfCtxVar(binding.from_var) : null;
  const targetKind = binding.to_agent_item_id === CTX_ID ? kindOfCtxVar(binding.to_var) : null;

  if (sourceKind === "locals" || targetKind === "locals") return "#f1c40f"; // yellow
  if (sourceKind === "inputs" || targetKind === "inputs") return "#2ea043"; // green
  if (sourceKind === "outputs" || targetKind === "outputs") return "#f85149"; // red
  return "#58a6ff"; // default blue
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

function moveCardToLane(itemId, fromLaneIdx, toLaneIdx, targetOrder = null) {
  if (!state.current?.graph) return;
  const fromLane = state.current.graph.lanes[fromLaneIdx];
  const toLane = state.current.graph.lanes[toLaneIdx];
  if (!fromLane || !toLane) return;
  const idx = fromLane.items.findIndex((i) => i.id === itemId);
  if (idx === -1) return;
  const [item] = fromLane.items.splice(idx, 1);
  const insertAtRaw = targetOrder ?? toLane.items.length;
  const adjustedInsert = fromLaneIdx === toLaneIdx && idx < insertAtRaw ? insertAtRaw - 1 : insertAtRaw;
  const insertAt = Math.min(Math.max(adjustedInsert, 0), toLane.items.length);
  if (!item.ui) item.ui = { lane_index: toLaneIdx, order: insertAt };
  item.ui.lane_index = toLaneIdx;
  item.ui.order = insertAt;
  toLane.items.splice(insertAt, 0, item);
  normalizeLaneOrders();
  renderCanvas();
}

function findDropIndex(laneEl, clientY, draggingId) {
  const cards = Array.from(laneEl.querySelectorAll(".agent-card"));
  const idx = cards.findIndex((card) => {
    if (card.dataset.itemId === String(draggingId)) return false;
    const rect = card.getBoundingClientRect();
    return clientY < rect.top + rect.height / 2;
  });
  return idx === -1 ? cards.length : idx;
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
  const isProtectedStopInput = kind === "inputs" && variable.name === STOP_AGENT_INPUT;
  const port = document.createElement("div");
  port.className = `port port-ctx port-${role}`;
  port.dataset.itemId = CTX_ID;
  port.dataset.varName = variable.name;
  port.dataset.role = role;

  const main = document.createElement("div");
  main.className = "port-main";
  const icon = document.createElement("span");
  icon.className = "port-icon";
  main.appendChild(icon);
  const label = document.createElement("span");
  label.textContent = variable.name;
  main.appendChild(label);
  if (kind === "locals") {
    const valInput = document.createElement("input");
    valInput.type = "text";
    valInput.className = "var-value-input";
    valInput.value = variable.value !== undefined ? JSON.stringify(variable.value) : "";
    valInput.title = "Значення локальної змінної (JSON дозволено)";
    ["mousedown", "click", "dblclick"].forEach((evt) => {
      valInput.addEventListener(evt, (e) => {
        e.stopPropagation();
      });
    });
    valInput.addEventListener("change", (e) => {
      updateLocalVarValue(variable.name, e.target.value);
    });
    valInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        updateLocalVarValue(variable.name, e.target.value);
      }
    });
    main.appendChild(valInput);
  }
  port.appendChild(main);

  const actions = document.createElement("div");
  actions.className = "port-actions";
  if (!isProtectedStopInput) {
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
  }
  port.appendChild(actions);

  port.addEventListener("mousedown", (e) => {
    if (e.target.closest(".port-actions") || e.target.closest(".var-value-input")) return;
    startDrag(e, CTX_ID, variable.name, role);
  });
  port.addEventListener("mouseup", (e) => {
    if (e.target.closest(".port-actions") || e.target.closest(".var-value-input")) return;
    finishDrag(e, CTX_ID, variable.name, role);
  });
  return port;
}

function updateLocalVarValue(varName, rawValue) {
  if (!state.current) return;
  const idx = state.current.locals.findIndex((v) => v.name === varName);
  if (idx === -1) return;
  const parsedValue = parseValueInput(rawValue, state.current.locals[idx].value);
  state.current.locals[idx] = { ...state.current.locals[idx], value: parsedValue };
  renderCanvas();
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
  if (kind === "inputs" && varName === STOP_AGENT_INPUT) {
    setStatus("Системна змінна не може бути змінена", "warn");
    return;
  }
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
  if (kind === "inputs" && varName === STOP_AGENT_INPUT) {
    setStatus("Системну змінну не можна видалити", "warn");
    return;
  }
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

function dropBindingsForItem(itemId) {
  if (!state.current?.graph) return;
  state.current.graph.lanes.forEach((lane) => {
    lane.items.forEach((item) => {
      item.bindings = (item.bindings || []).filter(
        (b) => b.from_agent_item_id !== itemId && b.to_agent_item_id !== itemId,
      );
    });
  });
  state.current.graph.ctx_bindings = (state.current.graph.ctx_bindings || []).filter(
    (b) => b.from_agent_item_id !== itemId && b.to_agent_item_id !== itemId,
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
  if (kind === "inputs" && name === STOP_AGENT_INPUT) {
    setStatus("Ця змінна зарезервована та створена автоматично", "warn");
    return;
  }
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

function setupZoomControls() {
  const slider = $("canvasScale");
  const valueLabel = $("canvasScaleValue");
  if (!slider) return;
  const update = (val) => {
    state.canvasScale = val / 100;
    if (valueLabel) valueLabel.textContent = `${val}%`;
    renderCanvas();
  };
  slider.addEventListener("input", (e) => update(Number(e.target.value)));
  update(Number(slider.value || 100));
}

function setupNameInput() {
  const input = getNameInput();
  if (!input) return;
  input.addEventListener("input", () => {
    applyNameFromInput(false);
  });
  input.addEventListener("blur", () => {
    applyNameFromInput(true);
  });
  syncNameInput();
}

function bindEvents() {
  $("btnNew")?.addEventListener("click", newAgent);
  $("btnSave")?.addEventListener("click", saveAgent);
  $("btnCreate")?.addEventListener("click", createAgent);
  $("btnAddLane")?.addEventListener("click", () => addLane());
  $("btnAddLaneAfter")?.addEventListener("click", addLaneAfterActive);
  document.addEventListener("mouseup", () => {
    state.drag = null;
  });
  setupZoneButtons();
  setupZoomControls();
  setupNameInput();
}

window.addEventListener("resize", () => {
  syncTopbarHeight();
  scheduleDrawBindings();
});

syncTopbarHeight();
bindEvents();
loadAgentsList();
newAgent();
