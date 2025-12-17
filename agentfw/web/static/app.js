/* eslint-disable no-console */
const state = {
  agents: [],
  cache: {},
  current: null,
  selectedChild: null,
  linkDraft: null,
  childCounter: 1,
};

const VAR_TYPES = ["string", "int", "float", "bool", "object", "array"];

function $(id) {
  return document.getElementById(id);
}

function safe(el, fn) {
  if (!el) return;
  fn(el);
}

function setStatus(message, tone = "info") {
  const el = $("status");
  if (!el) return;
  el.textContent = message;
  el.hidden = !message;
  el.classList.toggle("warning", tone === "error");
}

async function fetchJSON(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return resp.json();
}

function emptyAgent() {
  return {
    id: "",
    name: "",
    description: null,
    inputs: [],
    locals: [],
    outputs: [],
    children: {},
    lanes: [{ id: "lane-1", agents: [] }],
    links: [],
  };
}

function renderAgentsList() {
  const list = $("agentList");
  if (!list) return;
  list.innerHTML = "";
  const query = ($("agentSearch")?.value || "").toLowerCase();
  state.agents
    .filter((a) => !query || a.name.toLowerCase().includes(query) || a.id.toLowerCase().includes(query))
    .forEach((agent) => {
      const li = document.createElement("li");
      li.draggable = true;
      li.dataset.agentId = agent.id;
      li.addEventListener("dragstart", (e) => {
        e.dataTransfer?.setData("application/agent-id", agent.id);
      });
      const span = document.createElement("span");
      span.textContent = agent.name || agent.id;
      li.appendChild(span);
      const btn = document.createElement("button");
      btn.textContent = "Відкрити";
      btn.addEventListener("click", () => loadAgent(agent.id));
      li.appendChild(btn);
      list.appendChild(li);
    });

  const runSelect = $("runAgentSelect");
  if (runSelect) {
    runSelect.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "— оберіть агента —";
    runSelect.appendChild(placeholder);
    state.agents.forEach((a) => {
      const opt = document.createElement("option");
      opt.value = a.id;
      opt.textContent = a.name || a.id;
      runSelect.appendChild(opt);
    });
  }
}

async function loadAgents() {
  try {
    const data = await fetchJSON("/api/agents");
    state.agents = data.agents || [];
    renderAgentsList();
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити бібліотеку агентів", "error");
  }
}

function updateAgentFields() {
  safe($("agentId"), (el) => {
    el.value = state.current?.id || "";
  });
  safe($("agentName"), (el) => {
    el.value = state.current?.name || "";
  });
}

function updateVariable(kind, index, changes) {
  if (!state.current) return;
  const list = state.current[kind];
  if (!Array.isArray(list) || !list[index]) return;
  state.current[kind][index] = { ...list[index], ...changes };
  renderVariables();
}

function removeVariable(kind, index) {
  if (!state.current) return;
  const list = state.current[kind];
  if (!Array.isArray(list) || !list[index]) return;
  const name = list[index].name;
  const addressPrefix = kind === "inputs" ? "$in" : kind === "locals" ? "$local" : "$out";
  const used = (state.current.links || []).some(
    (link) => link.src === `${addressPrefix}.${name}` || link.dst === `${addressPrefix}.${name}`,
  );
  if (used) {
    setStatus("Неможливо видалити: змінна використовується у з’єднаннях", "error");
    return;
  }
  list.splice(index, 1);
  renderVariables();
}

function addVariable(kind) {
  if (!state.current) return;
  state.current[kind].push({ name: `${kind}_${state.current[kind].length + 1}`, type: "string", required: false });
  renderVariables();
}

function renderVariables() {
  ["inputs", "locals", "outputs"].forEach((kind) => {
    const container = $(`${kind}List`);
    if (!container || !state.current) return;
    container.innerHTML = "";
    state.current[kind].forEach((v, idx) => {
      const row = document.createElement("div");
      row.className = "var-row";

      const nameInput = document.createElement("input");
      nameInput.value = v.name;
      nameInput.addEventListener("change", (e) => updateVariable(kind, idx, { name: e.target.value }));
      row.appendChild(nameInput);

      const typeSelect = document.createElement("select");
      VAR_TYPES.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        if (t === v.type) opt.selected = true;
        typeSelect.appendChild(opt);
      });
      typeSelect.addEventListener("change", (e) => updateVariable(kind, idx, { type: e.target.value }));
      row.appendChild(typeSelect);

      const req = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = !!v.required;
      checkbox.addEventListener("change", (e) => updateVariable(kind, idx, { required: e.target.checked }));
      req.appendChild(checkbox);
      const small = document.createElement("span");
      small.textContent = "обов’язково";
      req.appendChild(small);
      row.appendChild(req);

      const del = document.createElement("button");
      del.textContent = "✕";
      del.addEventListener("click", () => removeVariable(kind, idx));
      row.appendChild(del);

      container.appendChild(row);
    });
  });
  renderPorts();
}

function renderPorts() {
  const rootPorts = [
    { list: "inputsList", prefix: "$in" },
    { list: "localsList", prefix: "$local" },
    { list: "outputsList", prefix: "$out" },
  ];
  rootPorts.forEach(({ list, prefix }) => {
    const container = $(list);
    if (!container || !state.current) return;
    container.querySelectorAll(".port").forEach((p) => p.remove());
    (state.current[prefix === "$in" ? "inputs" : prefix === "$local" ? "locals" : "outputs"] || []).forEach(
      (decl) => {
        const port = document.createElement("div");
        port.className = "port";
        port.textContent = `${decl.name} (${decl.type})`;
        port.dataset.address = `${prefix}.${decl.name}`;
        attachPortEvents(port);
        container.appendChild(port);
      },
    );
  });
}

function attachPortEvents(el) {
  el.addEventListener("mousedown", () => {
    state.linkDraft = el.dataset.address;
  });
  el.addEventListener("mouseup", () => {
    if (!state.linkDraft || state.linkDraft === el.dataset.address) return;
    addLink(state.linkDraft, el.dataset.address);
    state.linkDraft = null;
  });
}

function addLink(src, dst) {
  if (!state.current) return;
  const exists = state.current.links.some((l) => l.src === src && l.dst === dst);
  if (exists) return;
  state.current.links.push({ src, dst });
  renderLinks();
}

function removeLink(idx) {
  if (!state.current) return;
  state.current.links.splice(idx, 1);
  renderLinks();
}

function renderLinks() {
  const list = $("linksList");
  if (!list || !state.current) return;
  list.innerHTML = "";
  state.current.links.forEach((link, idx) => {
    const li = document.createElement("li");
    li.textContent = `${link.src} → ${link.dst}`;
    const btn = document.createElement("button");
    btn.textContent = "✕";
    btn.addEventListener("click", () => removeLink(idx));
    li.appendChild(btn);
    list.appendChild(li);
  });
}

function renderInspector() {
  const inspector = $("inspector");
  if (!inspector) return;
  inspector.innerHTML = "";
  if (!state.selectedChild || !state.current) {
    inspector.textContent = "Оберіть дочірній агент";
    return;
  }
  const child = state.current.children[state.selectedChild];
  if (!child) {
    inspector.textContent = "Оберіть дочірній агент";
    return;
  }

  const title = document.createElement("h3");
  title.textContent = `Child ${child.id}`;
  inspector.appendChild(title);

  const runIfLabel = document.createElement("label");
  runIfLabel.textContent = "Умова виконання (run_if)";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "$local.flag == true";
  input.value = child.run_if || "";
  input.addEventListener("change", (e) => {
    child.run_if = e.target.value;
  });
  runIfLabel.appendChild(input);
  inspector.appendChild(runIfLabel);
}

function getAgentDefinition(agentId) {
  if (state.cache[agentId]) return Promise.resolve(state.cache[agentId]);
  return fetchJSON(`/api/agents/${agentId}`)
    .then((data) => {
      state.cache[agentId] = data;
      return data;
    })
    .catch((err) => {
      console.error(err);
      return null;
    });
}

async function renderLanes() {
  const lanes = $("lanes");
  if (!lanes || !state.current) return;
  lanes.innerHTML = "";
  for (const lane of state.current.lanes) {
    const laneEl = document.createElement("div");
    laneEl.className = "lane";
    laneEl.dataset.laneId = lane.id;
    laneEl.addEventListener("dragover", (e) => e.preventDefault());
    laneEl.addEventListener("drop", (e) => handleDrop(e, lane.id));

    const header = document.createElement("div");
    header.className = "lane-header";
    const title = document.createElement("strong");
    title.textContent = `Смуга ${lane.id}`;
    header.appendChild(title);
    laneEl.appendChild(header);

    for (const childId of lane.agents) {
      const child = state.current.children[childId];
      if (!child) continue;
      const card = document.createElement("div");
      card.className = "child-card";
      card.draggable = true;
      card.dataset.childId = child.id;
      card.addEventListener("dragstart", (e) => {
        e.dataTransfer?.setData("application/child-id", child.id);
      });
      card.addEventListener("click", () => {
        state.selectedChild = child.id;
        renderInspector();
      });

      const titleRow = document.createElement("div");
      titleRow.className = "child-title";
      const name = document.createElement("strong");
      name.textContent = child.ref;
      titleRow.appendChild(name);
      if (child.run_if) {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "run_if";
        titleRow.appendChild(badge);
      }
      card.appendChild(titleRow);

      const ports = document.createElement("div");
      ports.className = "ports";
      const inputsCol = document.createElement("div");
      inputsCol.className = "port-column";
      const outputsCol = document.createElement("div");
      outputsCol.className = "port-column";
      const def = await getAgentDefinition(child.ref);
      (def?.inputs || []).forEach((v) => {
        const port = document.createElement("div");
        port.className = "port";
        port.textContent = `${v.name}`;
        port.dataset.address = `${child.id}.$in.${v.name}`;
        attachPortEvents(port);
        inputsCol.appendChild(port);
      });
      (def?.outputs || []).forEach((v) => {
        const port = document.createElement("div");
        port.className = "port";
        port.textContent = `${v.name}`;
        port.dataset.address = `${child.id}.$out.${v.name}`;
        attachPortEvents(port);
        outputsCol.appendChild(port);
      });
      ports.appendChild(inputsCol);
      ports.appendChild(outputsCol);
      card.appendChild(ports);

      laneEl.appendChild(card);
    }

    lanes.appendChild(laneEl);
  }
}

function handleDrop(event, laneId) {
  event.preventDefault();
  if (!state.current) return;
  const agentId = event.dataTransfer?.getData("application/agent-id");
  const childId = event.dataTransfer?.getData("application/child-id");
  if (agentId) {
    const newChildId = `child-${state.childCounter++}`;
    state.current.children[newChildId] = { id: newChildId, ref: agentId };
    const lane = state.current.lanes.find((l) => l.id === laneId);
    if (lane) lane.agents.push(newChildId);
  } else if (childId) {
    const lane = state.current.lanes.find((l) => l.id === laneId);
    if (!lane) return;
    state.current.lanes.forEach((l) => {
      l.agents = l.agents.filter((id) => id !== childId);
    });
    lane.agents.push(childId);
  }
  renderLanes();
  renderInspector();
}

async function loadAgent(agentId) {
  try {
    const data = await fetchJSON(`/api/agents/${agentId}`);
    state.current = {
      id: data.id,
      name: data.name,
      description: data.description || null,
      inputs: data.inputs || [],
      locals: data.locals || [],
      outputs: data.outputs || [],
      children: data.children || {},
      lanes: data.lanes || [],
      links: data.links || [],
    };
    updateAgentFields();
    renderVariables();
    renderLanes();
    renderLinks();
    renderInspector();
    setStatus(`Завантажено агента ${agentId}`);
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося завантажити агента", "error");
  }
}

async function saveAgent() {
  if (!state.current) {
    setStatus("Немає агента для збереження", "error");
    return;
  }
  const idInput = $("agentId");
  const nameInput = $("agentName");
  if (idInput) state.current.id = idInput.value.trim();
  if (nameInput) state.current.name = nameInput.value.trim();
  if (!state.current.id) {
    setStatus("Потрібен id агента", "error");
    return;
  }
  try {
    const resp = await fetch(`/api/agents/${state.current.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.current),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    setStatus("Збережено");
    loadAgents();
  } catch (err) {
    console.error(err);
    setStatus("Помилка збереження", "error");
  }
}

async function runAgent() {
  const agentId = $("runAgentSelect")?.value || "";
  if (!agentId) {
    setStatus("Оберіть агента для запуску", "error");
    return;
  }
  let inputPayload = {};
  let localsPayload = {};
  try {
    inputPayload = $("runInput")?.value ? JSON.parse($("runInput").value) : {};
    localsPayload = $("runLocals")?.value ? JSON.parse($("runLocals").value) : {};
  } catch (err) {
    setStatus("Некоректний JSON", "error");
    return;
  }
  try {
    const data = await fetchJSON("/api/agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, input_json: inputPayload, locals_json: localsPayload }),
    });
    safe($("runOutput"), (el) => {
      el.textContent = JSON.stringify(data.out, null, 2);
    });
    safe($("runTrace"), (el) => {
      el.textContent = JSON.stringify(data.trace, null, 2);
    });
    safe($("runStatus"), (el) => {
      el.textContent = data.failed ? "Помилка" : "Успішно";
    });
  } catch (err) {
    console.error(err);
    setStatus("Не вдалося запустити агента", "error");
  }
}

function bindEvents() {
  safe($("refreshAgents"), (btn) => btn.addEventListener("click", loadAgents));
  safe($("agentSearch"), (input) => input.addEventListener("input", renderAgentsList));
  safe($("newAgent"), (btn) =>
    btn.addEventListener("click", () => {
      state.current = emptyAgent();
      state.selectedChild = null;
      updateAgentFields();
      renderVariables();
      renderLanes();
      renderLinks();
      renderInspector();
      setStatus("Новий агент створено");
    }),
  );
  safe($("saveAgent"), (btn) => btn.addEventListener("click", saveAgent));
  safe($("addLane"), (btn) =>
    btn.addEventListener("click", () => {
      if (!state.current) return;
      const id = `lane-${state.current.lanes.length + 1}`;
      state.current.lanes.push({ id, agents: [] });
      renderLanes();
    }),
  );
  document.querySelectorAll("button[data-add-var]").forEach((btn) => {
    btn.addEventListener("click", () => addVariable(btn.dataset.addVar));
  });
  safe($("runAgent"), (btn) => btn.addEventListener("click", runAgent));
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadAgents();
  state.current = emptyAgent();
  updateAgentFields();
  renderVariables();
  renderLanes();
  renderLinks();
  renderInspector();
});
