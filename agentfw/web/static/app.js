const t = {
  selectStep: 'Оберіть крок, щоб редагувати.',
  saved: 'Успішно збережено!',
  saveFailed: 'Помилка збереження',
  validationOk: 'Опис валідний',
  validationFail: 'Помилка валідації',
  agentRunError: 'Помилка запуску агента',
};

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
  agentsGraph: { agents: [], edges: [] },
};

const canvas = document.getElementById('graphCanvas');
const ctx = canvas.getContext('2d');

function toolLabel(tool) {
  if (typeof tool === 'string') return tool;
  return tool.label_uk || tool.name || '';
}

function toolDescription(tool) {
  if (typeof tool === 'string') return '';
  return tool.description_uk || tool.description || '';
}

function updateToolDescription(name) {
  const el = document.getElementById('toolDescription');
  if (!el) return;
  const meta = state.tools.find((t) => t.name === name);
  el.textContent = toolDescription(meta);
}

function getConditionMeta(type) {
  return state.conditions.find((c) => c.type === type);
}

function fetchConditionFieldValue(container, name) {
  const el = container.querySelector(`[data-cond-field="${name}"]`);
  if (!el) return undefined;
  const value = el.value;
  return value === '' ? undefined : value;
}

function knownVariables() {
  const vars = new Set();
  Object.values(state.steps).forEach((step) => {
    Object.keys(step.save_mapping || {}).forEach((k) => vars.add(k));
  });
  return Array.from(vars);
}

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
  fetchAgentsGraph();
}

function renderToolPalette() {
  const palette = document.getElementById('toolPalette');
  palette.innerHTML = '';
  state.tools.forEach((tool) => {
    const pill = document.createElement('div');
    pill.className = 'tool-pill';
    pill.draggable = true;
    const title = document.createElement('strong');
    title.textContent = toolLabel(tool);
    const desc = document.createElement('span');
    desc.textContent = toolDescription(tool);
    desc.className = 'muted';
    pill.appendChild(title);
    if (desc.textContent) pill.appendChild(desc);
    pill.title = toolDescription(tool);
    pill.dataset.tool = tool.name || tool;
    pill.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', pill.dataset.tool);
    });
    palette.appendChild(pill);
  });
}

function populateToolAndConditionOptions() {
  const toolSelect = document.getElementById('toolName');
  toolSelect.innerHTML = '<option value="">—</option>';
  state.tools.forEach((tool) => {
    const opt = document.createElement('option');
    opt.value = tool.name || tool;
    opt.textContent = toolLabel(tool);
    opt.dataset.description = toolDescription(tool);
    toolSelect.appendChild(opt);
  });

  const condSelect = document.getElementById('conditionType');
  condSelect.innerHTML = '';
  state.conditions.forEach((cond) => {
    const opt = document.createElement('option');
    opt.value = cond.type || cond;
    opt.textContent = cond.label_uk || cond.type;
    condSelect.appendChild(opt);
  });

  renderConditionFields(condSelect.value);
}

function renderConditionFields(selectedType) {
  const container = document.getElementById('conditionFields');
  container.innerHTML = '';
  const meta = getConditionMeta(selectedType) || { fields: [] };
  (meta.fields || []).forEach((field) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'field-group';
    const label = document.createElement('label');
    label.textContent = field.label_uk || field.name;
    const input = document.createElement('input');
    input.dataset.condField = field.name;
    wrapper.appendChild(label);
    wrapper.appendChild(input);
    container.appendChild(wrapper);
  });
}

function populateAgentOptions() {
  const select = document.getElementById('agentSelect');
  select.innerHTML = '<option value="">— оберіть наявного —</option>';
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
    tool_params: step.tool_params || {},
    save_mapping: step.save_mapping || {},
    validator_params: step.validator_params || {},
    validator_policy: step.validator_policy || {},
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
      updatePreview();
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

function renderSaveMappingRows(step) {
  const container = document.getElementById('saveMappingRows');
  container.innerHTML = '';
  const entries = Object.entries(step.save_mapping || {});
  if (!entries.length) {
    const info = document.createElement('p');
    info.className = 'muted';
    info.textContent = 'Немає правил збереження.';
    container.appendChild(info);
  }
  entries.forEach(([varName, resultKey], idx) => {
    const row = document.createElement('div');
    row.className = 'save-row';
    const varInput = document.createElement('input');
    varInput.value = varName;
    varInput.placeholder = 'Змінна стану';
    varInput.dataset.rowIndex = idx;
    varInput.dataset.kind = 'var';

    const resultInput = document.createElement('input');
    resultInput.value = resultKey;
    resultInput.placeholder = 'Ключ у результаті';
    resultInput.dataset.rowIndex = idx;
    resultInput.dataset.kind = 'result';

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = '✕';
    removeBtn.addEventListener('click', () => {
      const mapping = Object.entries(step.save_mapping || {});
      mapping.splice(idx, 1);
      step.save_mapping = Object.fromEntries(mapping);
      renderSaveMappingRows(step);
      renderInspector(step);
      updatePreview();
    });

    [varInput, resultInput].forEach((input) => {
      input.addEventListener('input', () => {
        const mapping = Object.entries(step.save_mapping || {});
        mapping[idx] = [varInput.value.trim(), resultInput.value.trim()];
        step.save_mapping = Object.fromEntries(mapping.filter(([k, v]) => k && v));
        updatePreview();
      });
    });

    row.appendChild(varInput);
    row.appendChild(resultInput);
    row.appendChild(removeBtn);
    container.appendChild(row);
  });
}

function selectStep(stepId) {
  state.selectedStepId = stepId;
  const step = state.steps[stepId];
  if (!step) {
    document.getElementById('inspectorContent').textContent = t.selectStep;
    return;
  }

  document.getElementById('stepId').value = step.id;
  document.getElementById('stepName').value = step.name || '';
  document.getElementById('stepKind').value = step.kind || '';
  document.getElementById('toolName').value = step.tool_name || '';
  updateToolDescription(step.tool_name || '');
  document.getElementById('toolParams').value = JSON.stringify(step.tool_params || {}, null, 2);
  document.getElementById('validatorAgent').value = step.validator_agent_name || '';
  document.getElementById('validatorParams').value = JSON.stringify(step.validator_params || {}, null, 2);
  document.getElementById('validatorPolicy').value = JSON.stringify(step.validator_policy || {}, null, 2);

  renderSaveMappingRows(step);
  renderInspector(step);
  render();
}

function renderInspector(step) {
  const panel = document.getElementById('inspectorContent');
  if (!step) {
    panel.textContent = t.selectStep;
    return;
  }

  const inputs = Object.keys(step.tool_params || {});
  const outputs = Object.keys(step.save_mapping || {});
  const vars = knownVariables();

  panel.innerHTML = `
    <div class="inspector-row"><strong>${step.id}</strong><span class="badge">${
    state.entryStepId === step.id ? 'entry' : 'step'
  }</span></div>
    <div class="inspector-row"><span>Інструмент</span><span>${toolLabel(
      state.tools.find((t) => t.name === step.tool_name) || step.tool_name || '—',
    )}</span></div>
    <div class="inspector-row"><span>Тип</span><span>${step.kind || 'tool'}</span></div>
    <div class="inspector-row"><span>Валідатор</span><span>${
      step.validator_agent_name || '—'
    }</span></div>
    <div class="inspector-row"><span>Відомі змінні</span><span class="pill-list" data-role="known-vars"></span></div>
    <div class="inspector-row"><span>Вхідні поля</span><span class="pill-list" data-role="inputs"></span></div>
    <div class="inspector-row"><span>Результати</span><span class="pill-list" data-role="outputs"></span></div>
    <div class="connector-hint">Утримуйте Shift і тягніть зі step, щоб створити перехід.</div>
    <div class="actions">
      <button id="setEntryBtn">Зробити початковим</button>
      <button id="toggleEndBtn">${state.endStepIds.has(step.id) ? 'Прибрати кінець' : 'Позначити завершальним'}</button>
    </div>
  `;

  const knownContainer = document.createElement('div');
  knownContainer.className = 'pill-list';
  (vars.length ? vars : ['—']).forEach((k) => {
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = k;
    knownContainer.appendChild(span);
  });

  const inputsContainer = document.createElement('div');
  inputsContainer.className = 'pill-list';
  (inputs.length ? inputs : ['—']).forEach((k) => {
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = k;
    inputsContainer.appendChild(span);
  });

  const outputsContainer = document.createElement('div');
  outputsContainer.className = 'pill-list';
  (outputs.length ? outputs : ['—']).forEach((k) => {
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = k;
    outputsContainer.appendChild(span);
  });

  panel.querySelector('[data-role="inputs"]')?.replaceWith(inputsContainer);
  panel.querySelector('[data-role="outputs"]')?.replaceWith(outputsContainer);
  panel.querySelector('[data-role="known-vars"]')?.replaceWith(knownContainer);

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

  renderTransitionList(step);
}

function parseJsonField(value) {
  if (!value || !value.trim()) return {};
  return JSON.parse(value);
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
      const angle = Math.atan2(endY - startY, endX - startX);
      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(endX - 8 * Math.cos(angle - Math.PI / 6), endY - 8 * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(endX - 8 * Math.cos(angle + Math.PI / 6), endY - 8 * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fillStyle = '#1d5dff';
      ctx.fill();

      if (tr.condition?.type) {
        const meta = getConditionMeta(tr.condition.type);
        const label = meta?.label_uk || tr.condition.type;
        const midX = (startX + endX) / 2;
        const midY = (startY + endY) / 2;
        ctx.fillStyle = 'rgba(13, 27, 42, 0.7)';
        ctx.font = '11px Inter';
        ctx.fillText(label, midX + 4, midY - 4);
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

  Object.values(state.steps).forEach((step) => {
    ctx.fillStyle = state.selectedStepId === step.id ? '#e6f0ff' : '#fff';
    ctx.strokeStyle = '#1d3557';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(step.x, step.y, 140, 60, 8);
    } else {
      ctx.rect(step.x, step.y, 140, 60);
    }
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#0d1b2a';
    ctx.font = 'bold 13px Inter';
    ctx.fillText(step.id, step.x + 10, step.y + 20);
    ctx.font = '12px Inter';
    ctx.fillText(step.tool_name || '', step.x + 10, step.y + 38);
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
    alert('Вкажіть ім’я агента перед збереженням.');
    return;
  }
  const definition = collectDefinition();
  const res = await fetch(`/api/agents/${agentName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(definition),
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    alert(`${t.saveFailed}: ${data.error || res.statusText}`);
    return;
  }
  alert(t.saved);
  fetchAgents();
}

async function validateAgent() {
  try {
    const definition = collectDefinition();
    const res = await fetch('/api/agents/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(definition),
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      alert(`${t.validationFail}: ${data.error || res.statusText}`);
    } else {
      alert(t.validationOk);
    }
  } catch (err) {
    alert(`${t.validationFail}: ${err}`);
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

async function loadAgent(nameFromClick) {
  const manualName = document.getElementById('agentName').value.trim();
  const selectedName = document.getElementById('agentSelect').value;
  const agentName = typeof nameFromClick === 'string' ? nameFromClick : selectedName || manualName;
  if (!agentName) {
    alert('Вкажіть ім’я агента для завантаження.');
    return;
  }
  document.getElementById('agentName').value = agentName;
  document.getElementById('agentSelect').value = agentName;
  const res = await fetch(`/api/agents/${agentName}`);
  if (!res.ok) {
    alert('Агент не знайдений або YAML некоректний.');
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
  document.getElementById('inspectorContent').textContent = t.selectStep;
  document.getElementById('runAgentName').value = '';
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
  const type = document.getElementById('conditionType').value;
  const fieldContainer = document.getElementById('conditionFields');
  const condition = { type };
  const meta = getConditionMeta(type) || { fields: [] };
  (meta.fields || []).forEach((f) => {
    const value = fetchConditionFieldValue(fieldContainer, f.name);
    if (value !== undefined) condition[f.name] = value;
  });

  const step = state.steps[from];
  step.transitions = step.transitions || [];
  step.transitions.push({ target_step_id: to, condition });
  renderTransitionList(step);
  render();
  updatePreview();
}

function addStepFromForm(evt) {
  evt.preventDefault();
  const id = document.getElementById('stepId').value.trim();
  if (!id) return;
  try {
    const toolParams = parseJsonField(document.getElementById('toolParams').value || '{}');
    const validatorParams = parseJsonField(document.getElementById('validatorParams').value || '{}');
    const validatorPolicy = parseJsonField(document.getElementById('validatorPolicy').value || '{}');
    const existing = state.steps[id] || {};
    const step = {
      ...existing,
      id,
      name: document.getElementById('stepName').value,
      kind: document.getElementById('stepKind').value,
      tool_name: document.getElementById('toolName').value,
      tool_params: toolParams,
      save_mapping: existing.save_mapping || {},
      validator_agent_name: document.getElementById('validatorAgent').value,
      validator_params: validatorParams,
      validator_policy: validatorPolicy,
      transitions: existing.transitions || [],
    };
    addStep(step);
    if (!state.entryStepId) {
      state.entryStepId = id;
      document.getElementById('entryStep').value = id;
    }
    selectStep(id);
    updatePreview();
    render();
  } catch (err) {
    alert(`Помилка розбору JSON: ${err}`);
  }
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
    alert('Некоректний JSON: ' + err);
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

function renderTransitionList(step) {
  const container = document.getElementById('transitionList');
  if (!container) return;
  container.innerHTML = '';
  (step.transitions || []).forEach((tr, idx) => {
    const row = document.createElement('div');
    row.className = 'transition-row';

    const targetSelect = document.createElement('select');
    Object.keys(state.steps).forEach((id) => {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = id;
      targetSelect.appendChild(opt);
    });
    targetSelect.value = tr.target_step_id;

    const condSelect = document.createElement('select');
    state.conditions.forEach((cond) => {
      const opt = document.createElement('option');
      opt.value = cond.type;
      opt.textContent = cond.label_uk || cond.type;
      condSelect.appendChild(opt);
    });
    condSelect.value = tr.condition?.type || '';

    const fieldsWrapper = document.createElement('div');
    fieldsWrapper.className = 'transition-fields';

    const renderFields = () => {
      fieldsWrapper.innerHTML = '';
      const meta = getConditionMeta(condSelect.value) || { fields: [] };
      (meta.fields || []).forEach((f) => {
        const input = document.createElement('input');
        input.placeholder = f.label_uk || f.name;
        input.value = tr.condition?.[f.name] ?? '';
        input.addEventListener('input', () => {
          tr.condition = tr.condition || { type: condSelect.value };
          tr.condition[f.name] = input.value;
          updatePreview();
        });
        fieldsWrapper.appendChild(input);
      });
    };
    renderFields();

    targetSelect.addEventListener('change', () => {
      tr.target_step_id = targetSelect.value;
      updatePreview();
      render();
    });

    condSelect.addEventListener('change', () => {
      tr.condition = { type: condSelect.value };
      renderFields();
      render();
      updatePreview();
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Видалити';
    deleteBtn.addEventListener('click', () => {
      step.transitions.splice(idx, 1);
      renderTransitionList(step);
      render();
      updatePreview();
    });

    row.appendChild(targetSelect);
    row.appendChild(condSelect);
    row.appendChild(fieldsWrapper);
    row.appendChild(deleteBtn);
    container.appendChild(row);
  });
}

async function runAgent() {
  const agent = document.getElementById('runAgentName').value.trim() || document.getElementById('agentName').value.trim();
  let inputObj = {};
  try {
    inputObj = parseJsonField(document.getElementById('runInput').value || '{}');
  } catch (err) {
    alert(`Некоректний JSON вхідних даних: ${err}`);
    return;
  }
  if (!agent) {
    alert('Вкажіть агента для запуску.');
    return;
  }
  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent, input: inputObj }),
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    alert(`${t.agentRunError}: ${data.error || res.statusText}`);
    return;
  }
  renderRunOutput(data);
}

function renderRunOutput(data) {
  const container = document.getElementById('runOutput');
  container.innerHTML = '';
  const status = document.createElement('div');
  status.className = data.failed ? 'status-badge bad' : 'status-badge good';
  status.textContent = data.failed ? 'failed' : 'ok';
  container.appendChild(status);

  const finalState = document.createElement('div');
  finalState.className = 'final-state';
  finalState.innerHTML = '<h4>Фінальний стан</h4>';
  const table = document.createElement('table');
  Object.entries(data.final_state || {}).forEach(([k, v]) => {
    const row = document.createElement('tr');
    const keyCell = document.createElement('td');
    keyCell.textContent = k;
    const valCell = document.createElement('td');
    valCell.textContent = typeof v === 'object' ? JSON.stringify(v) : v;
    row.appendChild(keyCell);
    row.appendChild(valCell);
    table.appendChild(row);
  });
  finalState.appendChild(table);
  container.appendChild(finalState);

  const historyBlock = document.createElement('div');
  historyBlock.innerHTML = '<h4>Історія кроків</h4>';
  (data.history || []).forEach((h) => {
    const card = document.createElement('div');
    card.className = 'history-card';
    card.innerHTML = `
      <div><strong>Крок:</strong> ${h.step_id}</div>
      <div><strong>Інструмент:</strong> ${h.tool_name || '—'}</div>
      <div><strong>Вхідні:</strong> <code>${JSON.stringify(h.input_variables || {})}</code></div>
      <div><strong>Результат:</strong> <code>${JSON.stringify(h.tool_result || {})}</code></div>
      <div><strong>Валідатор:</strong> <code>${JSON.stringify(h.validator_result || {})}</code></div>
      <div><strong>Перехід:</strong> ${h.chosen_transition || '—'}</div>
      <div><strong>Помилка:</strong> ${h.error || '—'}</div>
    `;
    historyBlock.appendChild(card);
  });
  container.appendChild(historyBlock);
}

async function fetchAgentsGraph() {
  const res = await fetch('/api/agents_graph');
  if (!res.ok) return;
  const data = await res.json();
  state.agentsGraph = data;
  renderAgentsGraph();
}

function renderAgentsGraph() {
  const container = document.getElementById('agentsGraph');
  if (!container) return;
  container.innerHTML = '';
  const nodesWrap = document.createElement('div');
  nodesWrap.className = 'graph-nodes';
  (state.agentsGraph.agents || []).forEach((n) => {
    const node = document.createElement('button');
    node.className = 'agent-node';
    node.textContent = n.name;
    node.title = (n.sources || []).join(', ');
    node.addEventListener('click', () => loadAgent(n.name));
    nodesWrap.appendChild(node);
  });
  container.appendChild(nodesWrap);

  const edgesWrap = document.createElement('div');
  edgesWrap.className = 'graph-edges';
  (state.agentsGraph.edges || []).forEach((e) => {
    const edge = document.createElement('div');
    edge.className = `edge edge-${e.kind}`;
    const badge = `<span class="badge">${e.kind}</span>`;
    const step = e.step_id ? `<code>${e.step_id}</code>` : '';
    const tool = e.tool_name ? `<span class="muted">${e.tool_name}</span>` : '';
    edge.innerHTML = `<span>${e.from}</span> → <span>${e.to}</span> ${badge} ${step} ${tool}`;
    edgesWrap.appendChild(edge);
  });
  container.appendChild(edgesWrap);
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
  document.getElementById('importJson').addEventListener('click', importJson);
  document.getElementById('exportJson').addEventListener('click', exportJson);
  document.getElementById('conditionType').addEventListener('change', (e) => {
    renderConditionFields(e.target.value);
  });
  document.getElementById('toolName').addEventListener('change', (e) => {
    updateToolDescription(e.target.value);
  });
  document.getElementById('addSaveMapping').addEventListener('click', () => {
    const step = state.steps[state.selectedStepId];
    if (!step) return;
    step.save_mapping = step.save_mapping || {};
    const index = Object.keys(step.save_mapping).length + 1;
    step.save_mapping[`var_${index}`] = 'result_key';
    renderSaveMappingRows(step);
    renderInspector(step);
    updatePreview();
  });
  document.getElementById('runAgent').addEventListener('click', runAgent);

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
        renderTransitionList(fromStep);
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
