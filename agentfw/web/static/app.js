const state = {
  steps: {},
  entryStepId: '',
  endStepIds: new Set(),
  tools: [],
  conditions: [],
  dragging: null,
};

const canvas = document.getElementById('graphCanvas');
const ctx = canvas.getContext('2d');

async function fetchTools() {
  const res = await fetch('/api/tools');
  const data = await res.json();
  state.tools = data.tools || [];
  state.conditions = data.conditions || [];
  populateToolAndConditionOptions();
}

function populateToolAndConditionOptions() {
  const toolSelect = document.getElementById('toolName');
  toolSelect.innerHTML = '<option value="">--</option>';
  state.tools.forEach((tool) => {
    const opt = document.createElement('option');
    opt.value = tool;
    opt.textContent = tool;
    toolSelect.appendChild(opt);
  });

  const condSelect = document.getElementById('conditionType');
  condSelect.innerHTML = '';
  state.conditions.forEach((cond) => {
    const opt = document.createElement('option');
    opt.value = cond;
    opt.textContent = cond;
    condSelect.appendChild(opt);
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
    });
  });

  // Draw nodes
  Object.values(state.steps).forEach((step) => {
    const width = 140;
    const height = 60;
    ctx.fillStyle = state.entryStepId === step.id ? '#e8f1ff' : '#ffffff';
    ctx.strokeStyle = '#1d5dff';
    ctx.lineWidth = 2;
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
  const hit = Object.values(state.steps).find(
    (step) => offsetX >= step.x && offsetX <= step.x + 140 && offsetY >= step.y && offsetY <= step.y + 60,
  );
  if (hit) {
    state.dragging = { id: hit.id, dx: offsetX - hit.x, dy: offsetY - hit.y };
  }
}

function onDrag(event) {
  if (!state.dragging) return;
  const { offsetX, offsetY } = event;
  const step = state.steps[state.dragging.id];
  step.x = offsetX - state.dragging.dx;
  step.y = offsetY - state.dragging.dy;
  render();
}

function endDrag() {
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
  Object.entries(def.steps || {}).forEach(([id, step]) => {
    addStep({ id, ...step });
  });
  document.getElementById('entryStep').value = state.entryStepId;
  updatePreview();
  render();
}

async function loadAgent() {
  const agentName = document.getElementById('agentName').value.trim();
  if (!agentName) {
    alert('Provide an agent name to load.');
    return;
  }
  const res = await fetch(`/api/agents/${agentName}`);
  if (!res.ok) {
    alert('Agent not found.');
    return;
  }
  const data = await res.json();
  populateFromDefinition(data);
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

function init() {
  fetchTools();
  document.getElementById('stepForm').addEventListener('submit', addStepFromForm);
  document.getElementById('transitionForm').addEventListener('submit', addTransition);
  document.getElementById('saveAgent').addEventListener('click', saveAgent);
  document.getElementById('validateAgent').addEventListener('click', validateAgent);
  document.getElementById('loadAgent').addEventListener('click', loadAgent);
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
  canvas.addEventListener('mouseup', endDrag);
  canvas.addEventListener('mouseleave', endDrag);

  render();
}

init();
