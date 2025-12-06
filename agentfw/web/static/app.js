const state = {
  steps: {},
  entryStepId: '',
  endStepIds: new Set(),
  agents: [],
  tools: [],
  conditions: [],
  dragging: null,
  draggingLink: null,
  selectedStepId: null,
  counter: 1,
};

const canvas = document.getElementById('graphCanvas');
const ctx = canvas.getContext('2d');

async function fetchTools() {
  const res = await fetch('/api/tools');
  const data = await res.json();
  state.tools = data.tools || [];
  state.conditions = data.conditions || [];
  populateToolAndConditionOptions();
  renderToolPalette();
}

async function fetchAgents(autoLoadFirst = false) {
  const res = await fetch('/api/agents');
  if (!res.ok) return;
  const data = await res.json();
  state.agents = data.agents || [];
  populateAgentOptions();

  if (autoLoadFirst && state.agents.length) {
    await loadAgent(state.agents[0]);
    document.getElementById('agentSelect').value = state.agents[0];
  } else if (!state.agents.length) {
    newAgent(true);
  }
}

function renderToolPalette() {
  const palette = document.getElementById('toolPalette');
  palette.innerHTML = '';
  state.tools.forEach((tool) => {
    const pill = document.createElement('div');
    pill.className = 'tool-pill';
    pill.draggable = true;
    const title = document.createElement('strong');
    title.textContent = tool.name || tool;
    const desc = document.createElement('span');
    desc.textContent = tool.description || '';
    desc.className = 'muted';
    pill.appendChild(title);
    if (desc.textContent) pill.appendChild(desc);
    pill.title = tool.description || '';
    pill.dataset.tool = tool.name || tool;
    pill.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', pill.dataset.tool);
    });
    palette.appendChild(pill);
  });
}

function populateToolAndConditionOptions() {
  const toolSelect = document.getElementById('toolName');
  toolSelect.innerHTML = '<option value="">--</option>';
  state.tools.forEach((tool) => {
    const opt = document.createElement('option');
    opt.value = tool.name || tool;
    opt.textContent = tool.name || tool;
    toolSelect.appendChild(opt);
  });

  const condSelect = document.getElementById('conditionType');
  condSelect.innerHTML = '';
  state.conditions.forEach((cond) => {
    const opt = document.createElement('option');
    const value = cond.type || cond;
    opt.value = value;
    opt.textContent = value;
    condSelect.appendChild(opt);
  });
}

function populateAgentOptions() {
  const select = document.getElementById('agentSelect');
  select.innerHTML = '<option value="">-- select existing --</option>';
  state.agents.forEach((name) => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
}

function addStep(step) {
  if (!step.id) return;
  const defaultPosition = Object.keys(state.steps).length;
  state.steps[step.id] = {
    ...step,
    transitions: step.transitions || [],
    x: step.x ?? 80 + (defaultPosition % 4) * 180,
    y: step.y ?? 80 + Math.floor(defaultPosition / 4) * 140,
  };
  refreshSelectors();
  render();
}

function nextStepId(base = 'step') {
  let id = `${base}_${state.counter}`;
  while (state.steps[id]) {
    state.counter += 1;
    id = `${base}_${state.counter}`;
  }
  state.counter += 1;
  return id;
}

function refreshSelectors() {
  const ids = Object.keys(state.steps);
  const entrySelect = document.getElementById('entryStep');
  const fromSelect = document.getElementById('fromStep');
  const toSelect = document.getElementById('toStep');
  const endStepsContainer = document.getElementById('endSteps');

  [entrySelect, fromSelect, toSelect].forEach((sel) => {
    sel.innerHTML = '';
    ids.forEach((id) => {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = id;
      sel.appendChild(opt);
    });
  });

  endStepsContainer.innerHTML = '';
  ids.forEach((id) => {
    const label = document.createElement('label');
    label.className = 'step-chip';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = state.endStepIds.has(id);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        state.endStepIds.add(id);
      } else {
        state.endStepIds.delete(id);
      }
    });
    label.appendChild(checkbox);
    const text = document.createElement('span');
    text.textContent = id;
    label.appendChild(text);
    endStepsContainer.appendChild(label);
  });

  if (state.entryStepId && ids.includes(state.entryStepId)) {
    entrySelect.value = state.entryStepId;
  } else if (ids.length && !state.entryStepId) {
    state.entryStepId = ids[0];
    entrySelect.value = state.entryStepId;
  }
}

function getStepAt(x, y) {
  return Object.values(state.steps).find(
    (step) => x >= step.x && x <= step.x + 140 && y >= step.y && y <= step.y + 60,
  );
}

function selectStep(stepId) {
  state.selectedStepId = stepId;
  const step = state.steps[stepId];
  if (!step) {
    document.getElementById('inspectorContent').textContent = 'Select a step to see details.';
    return;
  }

  document.getElementById('stepId').value = step.id;
  document.getElementById('stepName').value = step.name || '';
  document.getElementById('stepKind').value = step.kind || '';
  document.getElementById('toolName').value = step.tool_name || '';
  document.getElementById('toolParams').value = JSON.stringify(step.tool_params || {}, null, 2);
  document.getElementById('saveMapping').value = JSON.stringify(step.save_mapping || {}, null, 2);
  document.getElementById('validatorAgent').value = step.validator_agent_name || '';
  document.getElementById('validatorParams').value = JSON.stringify(step.validator_params || {}, null, 2);
  document.getElementById('validatorPolicy').value = JSON.stringify(step.validator_policy || {}, null, 2);

  renderInspector(step);
  render();
}

function renderInspector(step) {
  const panel = document.getElementById('inspectorContent');
  if (!step) {
    panel.textContent = 'Select a step to see details.';
    return;
  }

  const inputKeys = Object.keys(step.tool_params || {});
  const outputKeys = Object.keys(step.save_mapping || {});

  panel.innerHTML = `
    <div class="inspector-row"><strong>${step.id}</strong><span class="badge">${
    state.entryStepId === step.id ? 'entry' : 'step'
  }</span></div>
    <div class="inspector-row"><span>Tool</span><span>${step.tool_name || '—'}</span></div>
    <div class="inspector-row"><span>Kind</span><span>${step.kind || 'tool'}</span></div>
    <div class="inspector-row"><span>Validator</span><span>${
      step.validator_agent_name || '—'
    }</span></div>
    <div class="inspector-row"><span>Inputs</span><span class="pill-list" data-role="inputs"></span></div>
    <div class="inspector-row"><span>Outputs</span><span class="pill-list" data-role="outputs"></span></div>
    <div class="connector-hint">Hold Shift and drag from this step to another to link them.</div>
    <div class="actions">
      <button id="setEntryBtn">Set as entry</button>
      <button id="toggleEndBtn">${state.endStepIds.has(step.id) ? 'Unset end' : 'Mark as end'}</button>
    </div>
  `;

  const inputsContainer = document.createElement('div');
  inputsContainer.className = 'pill-list';
  (inputKeys.length ? inputKeys : ['—']).forEach((k) => {
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = k;
    inputsContainer.appendChild(span);
  });

  const outputsContainer = document.createElement('div');
  outputsContainer.className = 'pill-list';
  (outputKeys.length ? outputKeys : ['—']).forEach((k) => {
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = k;
    outputsContainer.appendChild(span);
  });

  panel.querySelector('[data-role="inputs"]')?.replaceWith(inputsContainer);
  panel.querySelector('[data-role="outputs"]')?.replaceWith(outputsContainer);

  panel.querySelector('#setEntryBtn')?.addEventListener('click', () => {
    state.entryStepId = step.id;
    document.getElementById('entryStep').value = step.id;
    render();
    updatePreview();
  });

  panel.querySelector('#toggleEndBtn')?.addEventListener('click', () => {
    if (state.endStepIds.has(step.id)) {
      state.endStepIds.delete(step.id);
    } else {
      state.endStepIds.add(step.id);
    }
    refreshSelectors();
    renderInspector(step);
    render();
    updatePreview();
  });
}

function parseJsonField(value) {
  if (!value || !value.trim()) return {};
  try {
    return JSON.parse(value);
  } catch (err) {
    alert(`JSON parse error: ${err}`);
    throw err;
  }
}

function collectDefinition() {
  const agentName = document.getElementById('agentName').value.trim();
  const entryStepId = document.getElementById('entryStep').value || state.entryStepId;
  const stepsPayload = {};
  Object.values(state.steps).forEach((step) => {
    stepsPayload[step.id] = {
      name: step.name,
      kind: step.kind,
      tool_name: step.tool_name,
      tool_params: step.tool_params || {},
      save_mapping: step.save_mapping || {},
      validator_agent_name: step.validator_agent_name,
      validator_params: step.validator_params || {},
      validator_policy: step.validator_policy || {},
      transitions: step.transitions || [],
    };
  });

  return {
    name: agentName,
    entry_step_id: entryStepId,
    end_step_ids: Array.from(state.endStepIds),
    steps: stepsPayload,
  };
}

function updatePreview() {
  const def = collectDefinition();
  document.getElementById('rawJson').value = JSON.stringify(def, null, 2);
}

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#c8d1e1';
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  // Draw edges
  Object.values(state.steps).forEach((step) => {
    (step.transitions || []).forEach((tr) => {
      const target = state.steps[tr.target_step_id];
      if (!target) return;
      const startX = step.x + 70;
      const startY = step.y + 30;
      const endX = target.x + 70;
      const endY = target.y + 30;
      ctx.strokeStyle = '#1d5dff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
      // arrow head
      const angle = Math.atan2(endY - startY, endX - startX);
      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(endX - 8 * Math.cos(angle - Math.PI / 6), endY - 8 * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(endX - 8 * Math.cos(angle + Math.PI / 6), endY - 8 * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fillStyle = '#1d5dff';
      ctx.fill();

      if (tr.condition?.type) {
        const midX = (startX + endX) / 2;
        const midY = (startY + endY) / 2;
        ctx.fillStyle = 'rgba(13, 27, 42, 0.7)';
        ctx.font = '11px Inter';
        ctx.fillText(tr.condition.type, midX + 4, midY - 4);
      }
    });
  });

  if (state.draggingLink) {
    const source = state.steps[state.draggingLink.from];
    if (source) {
      const startX = source.x + 70;
      const startY = source.y + 30;
      const { x, y } = state.draggingLink;
      ctx.strokeStyle = '#f39c12';
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(x, y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // Draw nodes
  Object.values(state.steps).forEach((step) => {
    const width = 140;
    const height = 60;
    ctx.fillStyle = state.entryStepId === step.id ? '#e8f1ff' : '#ffffff';
    ctx.strokeStyle = '#1d5dff';
    ctx.lineWidth = state.selectedStepId === step.id ? 3 : 2;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(step.x, step.y, width, height, 10);
    } else {
      ctx.rect(step.x, step.y, width, height);
    }
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#0d1b2a';
    ctx.font = '14px Inter';
    ctx.fillText(step.id, step.x + 10, step.y + 20);
    ctx.fillStyle = '#5c677d';
    ctx.font = '12px Inter';
    ctx.fillText(step.tool_name || step.kind || 'step', step.x + 10, step.y + 38);
    if (state.endStepIds.has(step.id)) {
      ctx.fillStyle = '#0f9d58';
      ctx.font = '11px Inter';
      ctx.fillText('end', step.x + 10, step.y + 54);
    }
  });
}

function startDrag(event) {
  const { offsetX, offsetY } = event;
  const hit = getStepAt(offsetX, offsetY);
  if (hit && event.shiftKey) {
    state.draggingLink = { from: hit.id, x: offsetX, y: offsetY };
    return;
  }
  if (hit) {
    state.dragging = { id: hit.id, dx: offsetX - hit.x, dy: offsetY - hit.y };
    selectStep(hit.id);
  }
}

function onDrag(event) {
  const { offsetX, offsetY } = event;
  if (state.draggingLink) {
    state.draggingLink.x = offsetX;
    state.draggingLink.y = offsetY;
    render();
  }
  if (!state.dragging) return;
  const step = state.steps[state.dragging.id];
  step.x = offsetX - state.dragging.dx;
  step.y = offsetY - state.dragging.dy;
  render();
}

function endDrag() {
  if (state.draggingLink) {
    state.draggingLink = null;
    render();
  }
  state.dragging = null;
}

async function saveAgent() {
  const agentName = document.getElementById('agentName').value.trim();
  if (!agentName) {
    alert('Provide an agent name before saving.');
    return;
  }
  const definition = collectDefinition();
  const res = await fetch(`/api/agents/${agentName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(definition),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(`Save failed: ${data.error || res.statusText}`);
    return;
  }
  alert('Saved successfully!');
}

async function validateAgent() {
  const definition = collectDefinition();
  const res = await fetch('/api/agents/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(definition),
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    alert(`Validation error: ${data.error || res.statusText}`);
  } else {
    alert('Definition is valid!');
  }
}

function populateFromDefinition(def) {
  state.steps = {};
  state.endStepIds = new Set(def.end_step_ids || []);
  state.entryStepId = def.entry_step_id || '';
  state.selectedStepId = null;
  Object.entries(def.steps || {}).forEach(([id, step]) => {
    addStep({ id, ...step });
  });
  document.getElementById('entryStep').value = state.entryStepId;
  const ids = Object.keys(state.steps);
  if (state.entryStepId && state.steps[state.entryStepId]) {
    selectStep(state.entryStepId);
  } else if (ids.length) {
    selectStep(ids[0]);
  }
  updatePreview();
  render();
}

async function loadAgent() {
  const manualName = document.getElementById('agentName').value.trim();
  const selectedName = document.getElementById('agentSelect').value;
  const agentName = typeof arguments[0] === 'string' ? arguments[0] : selectedName || manualName;
  if (!agentName) {
    alert('Provide an agent name to load.');
    return;
  }
  document.getElementById('agentName').value = agentName;
  document.getElementById('agentSelect').value = agentName;
  const res = await fetch(`/api/agents/${agentName}`);
  if (!res.ok) {
    alert('Agent not found.');
    return;
  }
  const data = await res.json();
  populateFromDefinition(data);
}

function newAgent(seedStep = false) {
  const seed = typeof seedStep === 'boolean' ? seedStep : true;
  if (seedStep && typeof seedStep.preventDefault === 'function') {
    seedStep.preventDefault();
  }
  state.steps = {};
  state.endStepIds = new Set();
  state.entryStepId = '';
  state.selectedStepId = null;
  document.getElementById('agentName').value = 'new_agent';
  document.getElementById('agentSelect').value = '';
  document.getElementById('inspectorContent').textContent = 'Select a step to see details.';
  if (seed) {
    const tool = state.tools[0]?.name || state.tools[0];
    const id = 'init';
    addStep({ id, name: 'init', kind: 'tool', tool_name: tool });
    state.entryStepId = id;
    document.getElementById('entryStep').value = id;
    selectStep(id);
  }
  refreshSelectors();
  updatePreview();
  render();
}

function addTransition(evt) {
  evt.preventDefault();
  const from = document.getElementById('fromStep').value;
  const to = document.getElementById('toStep').value;
  if (!from || !to) return;
  const condition = {
    type: document.getElementById('conditionType').value,
    value_from: document.getElementById('conditionValueFrom').value || undefined,
    value: document.getElementById('conditionValue').value || undefined,
    expression: document.getElementById('conditionExpression').value || undefined,
  };
  const extra = parseJsonField(document.getElementById('conditionExtra').value || '{}');
  Object.entries(extra).forEach(([k, v]) => {
    if (condition[k] === undefined) condition[k] = v;
  });
  const step = state.steps[from];
  step.transitions = step.transitions || [];
  step.transitions.push({ target_step_id: to, condition });
  render();
  updatePreview();
}

function addStepFromForm(evt) {
  evt.preventDefault();
  const id = document.getElementById('stepId').value.trim();
  if (!id) return;
  const step = {
    id,
    name: document.getElementById('stepName').value,
    kind: document.getElementById('stepKind').value,
    tool_name: document.getElementById('toolName').value,
    tool_params: parseJsonField(document.getElementById('toolParams').value || '{}'),
    save_mapping: parseJsonField(document.getElementById('saveMapping').value || '{}'),
    validator_agent_name: document.getElementById('validatorAgent').value,
    validator_params: parseJsonField(document.getElementById('validatorParams').value || '{}'),
    validator_policy: parseJsonField(document.getElementById('validatorPolicy').value || '{}'),
  };
  addStep(step);
  if (!state.entryStepId) {
    state.entryStepId = id;
    document.getElementById('entryStep').value = id;
  }
  updatePreview();
  render();
}

function handleCanvasDrop(evt) {
  evt.preventDefault();
  const tool = evt.dataTransfer.getData('text/plain');
  if (!tool) return;
  const rect = canvas.getBoundingClientRect();
  const x = evt.clientX - rect.left - 70;
  const y = evt.clientY - rect.top - 30;
  const id = nextStepId(tool || 'step');
  addStep({ id, name: id, kind: 'tool', tool_name: tool, x, y });
  if (!state.entryStepId) {
    state.entryStepId = id;
    document.getElementById('entryStep').value = id;
  }
  selectStep(id);
  updatePreview();
}

function importJson() {
  try {
    const data = JSON.parse(document.getElementById('rawJson').value || '{}');
    populateFromDefinition(data);
  } catch (err) {
    alert('Invalid JSON: ' + err);
  }
}

function exportJson() {
  updatePreview();
  const blob = new Blob([document.getElementById('rawJson').value], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const agentName = document.getElementById('agentName').value.trim() || 'agent';
  a.href = url;
  a.download = `${agentName}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function init() {
  await fetchTools();
  document.getElementById('stepForm').addEventListener('submit', addStepFromForm);
  document.getElementById('transitionForm').addEventListener('submit', addTransition);
  document.getElementById('saveAgent').addEventListener('click', saveAgent);
  document.getElementById('validateAgent').addEventListener('click', validateAgent);
  document.getElementById('loadAgent').addEventListener('click', loadAgent);
  document.getElementById('newAgent').addEventListener('click', newAgent);
  document.getElementById('refreshAgents').addEventListener('click', () => fetchAgents());
  document.getElementById('agentSelect').addEventListener('change', (e) => {
    document.getElementById('agentName').value = e.target.value;
  });
  document.getElementById('entryStep').addEventListener('change', (e) => {
    state.entryStepId = e.target.value;
    render();
    updatePreview();
  });
  document.getElementById('rawJson').addEventListener('input', () => {
    // no-op; user can edit before importing
  });
  document.getElementById('importJson').addEventListener('click', importJson);
  document.getElementById('exportJson').addEventListener('click', exportJson);

  canvas.addEventListener('mousedown', startDrag);
  canvas.addEventListener('mousemove', onDrag);
  canvas.addEventListener('mouseup', (event) => {
    if (state.draggingLink) {
      const hit = getStepAt(event.offsetX, event.offsetY);
      if (hit && hit.id !== state.draggingLink.from) {
        const fromStep = state.steps[state.draggingLink.from];
        fromStep.transitions = fromStep.transitions || [];
        fromStep.transitions.push({ target_step_id: hit.id, condition: { type: 'always' } });
        refreshSelectors();
        updatePreview();
      }
      state.draggingLink = null;
      render();
      return;
    }
    endDrag();
  });
  canvas.addEventListener('mouseleave', endDrag);
  canvas.addEventListener('click', (event) => {
    const hit = getStepAt(event.offsetX, event.offsetY);
    if (hit) {
      selectStep(hit.id);
    }
  });
  canvas.addEventListener('dragover', (e) => e.preventDefault());
  canvas.addEventListener('drop', handleCanvasDrop);

  await fetchAgents(true);
  render();
}

init();
