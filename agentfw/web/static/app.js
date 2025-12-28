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
  transitionCounter: 1,
  agentsGraph: { agents: [], edges: [] },
  agentPaletteFilter: '',
  runAgentKnownVars: [],
  definitionInputVars: [],
};

const canvas = document.getElementById('graphCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;

const STEP_MIN_WIDTH = 170;
const STEP_LABEL_PADDING = 56;
const STEP_BASE_HEIGHT = 70;
const PORT_GAP = 18;
const PORT_RADIUS = 6;
const PORT_DETECTION_RADIUS = 10;
const AGENT_INPUT_NODE_ID = '__agent_input__';
const RAIL_MARGIN = 24;
const RAIL_PADDING = 30;

if (!canvas || !ctx) {
  console.error('graphCanvas не знайдено, канвас вимкнено');
}

function withElement(id, handler) {
  const el = document.getElementById(id);
  if (!el) {
    console.warn(`Елемент #${id} не знайдено`);
    return null;
  }
  handler(el);
  return el;
}

function appendRunAgentLog(message, level = 'info', extra) {
  const logEl = document.getElementById('runAgentLog');
  const ts = new Date().toISOString();
  const serializedExtra = (() => {
    if (extra === undefined) return '';
    if (typeof extra === 'string') return ` ${extra}`;
    try {
      return ` ${JSON.stringify(extra, null, 2)}`;
    } catch (err) {
      return ' [не вдалося серіалізувати додаткові дані]';
    }
  })();

  const line = `[${ts}] ${message}${serializedExtra}`;
  const consoleMethod = level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log';
  console[consoleMethod](line);

  if (!logEl) return;
  const div = document.createElement('div');
  div.textContent = line;
  if (level === 'error') div.classList.add('log-error');
  if (level === 'warn') div.classList.add('log-warn');
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function clearRunAgentLog() {
  const logEl = document.getElementById('runAgentLog');
  if (logEl) logEl.innerHTML = '';
}

function setBanner(message, kind = 'error') {
  const banner = document.getElementById('statusBanner');
  if (!banner) return;
  if (!message) {
    banner.hidden = true;
    return;
  }
  banner.textContent = message;
  banner.classList.toggle('info', kind === 'info');
  banner.hidden = false;
}

function defaultNameFromKind(kind) {
  switch (kind) {
    case 'decision':
      return 'Розгалуження';
    case 'loop':
      return 'Цикл';
    case 'validator':
      return 'Валідатор';
    default:
      return 'Крок дії';
  }
}

function generateStepId(base = 'step') {
  let id = `${base}_${state.counter}`;
  while (state.steps[id]) {
    state.counter += 1;
    id = `${base}_${state.counter}`;
  }
  state.counter += 1;
  return id;
}

function generateTransitionId() {
  const id = `tr_${state.transitionCounter}`;
  state.transitionCounter += 1;
  return id;
}

function toolLabel(tool) {
  if (typeof tool === 'string') return tool;
  return tool.label_uk || tool.name || '';
}

function toolDescription(tool) {
  if (typeof tool === 'string') return '';
  return tool.description_uk || tool.description || '';
}

function normalizeAgent(raw) {
  if (typeof raw === 'string') {
    return { id: raw, name: raw };
  }
  return {
    id: raw?.id || raw?.name || '',
    name: raw?.name || raw?.id || '',
  };
}

function addRunAgentVarRow(name = '', value = '', kind = 'custom') {
  const container = document.getElementById('runAgentVars');
  if (!container) return;

  const row = document.createElement('div');
  row.className = 'var-row';
  row.dataset.varKind = kind;

  let nameNode = null;

  if (kind === 'known' && name) {
    row.dataset.varName = name;
    const nameLabel = document.createElement('span');
    nameLabel.className = 'var-name-label';
    nameLabel.textContent = name;
    nameNode = nameLabel;
  } else {
    const customNameInput = document.createElement('input');
    customNameInput.className = 'var-name-custom';
    customNameInput.placeholder = 'Назва змінної';
    customNameInput.value = name;
    nameNode = customNameInput;
  }

  const valueInput = document.createElement('input');
  valueInput.className = 'var-value-input';
  valueInput.placeholder = 'Значення';
  valueInput.value = value;

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.textContent = '✕';
  removeBtn.addEventListener('click', () => {
    row.remove();
    ensureRunAgentRow();
  });

  row.appendChild(nameNode);
  row.appendChild(valueInput);
  row.appendChild(removeBtn);
  container.appendChild(row);
}

function ensureRunAgentRow() {
  const container = document.getElementById('runAgentVars');
  if (!container) return;
  if (!container.children.length) {
    addRunAgentVarRow();
  }
}

function collectRunAgentInput() {
  const container = document.getElementById('runAgentVars');
  if (!container) return {};
  const payload = {};

  container.querySelectorAll('.var-row').forEach((row) => {
    const valueInput = row.querySelector('.var-value-input');
    const customNameInput = row.querySelector('.var-name-custom');
    const key = row.dataset.varName || customNameInput?.value?.trim();
    if (!key) return;
    const raw = valueInput.value;
    try {
      payload[key] = JSON.parse(raw);
    } catch (err) {
      payload[key] = raw;
    }
  });

  return payload;
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

function filterAgents(query = '') {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return state.agents;
  return state.agents.filter((a) => a.id.toLowerCase().includes(trimmed) || a.name.toLowerCase().includes(trimmed));
}

function knownVariables() {
  const vars = new Set();
  Object.values(state.steps).forEach((step) => {
    (step.saveMapping || []).forEach((m) => {
      if (m.varName) vars.add(m.varName);
    });
  });
  return Array.from(vars);
}

function normalizeCondition(raw = {}) {
  const type = raw.type || 'always';
  const params = { ...(raw.params || {}) };
  Object.entries(raw).forEach(([k, v]) => {
    if (k !== 'type' && k !== 'params') params[k] = v;
  });
  return { type, params };
}

function normalizeTransition(raw, parentStepId) {
  const normalized = {
    id: raw?.id || generateTransitionId(),
    targetStepId: raw?.target_step_id || raw?.targetStepId || raw?.target || parentStepId,
    condition: normalizeCondition(raw?.condition || raw || {}),
  };
  return normalized;
}

function normalizeSaveMapping(rawMapping) {
  if (Array.isArray(rawMapping)) return rawMapping;
  if (!rawMapping) return [];
  return Object.entries(rawMapping).map(([varName, resultKey]) => ({ varName, resultKey, description: '' }));
}

function normalizeStep(raw) {
  const id = raw.id;
  const defaultPosition = Object.keys(state.steps).length;
  const kind = raw.kind === 'tool' ? 'action' : raw.kind || 'action';
  const inputs = Array.isArray(raw.inputs)
    ? raw.inputs.map((inp) => ({
        name: inp?.name || inp?.input || '',
        fromVar: inp?.fromVar || inp?.from_var || '',
        fromStepId: inp?.fromStepId || inp?.from_step_id || '',
        defaultValue: inp?.defaultValue ?? inp?.default_value ?? '',
        description: inp?.description || '',
      }))
    : [];
  const rawLinks = Array.isArray(raw.input_links) ? raw.input_links : [];
  rawLinks.forEach((link) => {
    const idx =
      typeof link.input_index === 'number'
        ? link.input_index
        : inputs.findIndex((inp) => inp.name && inp.name === (link.input || link.input_name));
    if (idx >= 0 && inputs[idx]) {
      inputs[idx].fromStepId ||= link.from_step_id || link.fromStepId || '';
      inputs[idx].fromVar ||= link.from_var || link.varName || '';
    }
  });
  return {
    id,
    name: raw.name || defaultNameFromKind(kind),
    kind,
    toolName: raw.toolName || raw.tool_name || raw.tool || null,
    toolParams: raw.toolParams || raw.tool_params || {},
    inputs,
    saveMapping: normalizeSaveMapping(raw.saveMapping || raw.save_mapping),
    validatorAgentName: raw.validator_agent_name || raw.validatorAgentName || '',
    validatorParams: raw.validator_params || raw.validatorParams || {},
    validatorPolicy: raw.validator_policy || raw.validatorPolicy || {},
    transitions: (raw.transitions || []).map((tr) => normalizeTransition(tr, id)),
    x: raw.x ?? 80 + (defaultPosition % 4) * 180,
    y: raw.y ?? 80 + Math.floor(defaultPosition / 4) * 140,
  };
}

function createStep(kind, overrides = {}) {
  const id = overrides.id || generateStepId(kind);
  const base = normalizeStep({
    id,
    kind,
    name: overrides.name || defaultNameFromKind(kind),
    ...overrides,
  });
  if (kind === 'loop' && (!base.transitions || !base.transitions.length)) {
    base.transitions = base.transitions || [];
    base.transitions.push({
      id: generateTransitionId(),
      targetStepId: id,
      condition: { type: 'always', params: {} },
    });
  }
  state.steps[id] = base;
  state.entryStepId ??= id;
  state.selectedStepId = id;
  refreshSelectors();
  renderAll();
  return base;
}

function getStepSize(step) {
  const portCount = Math.max(step.inputs?.length || 0, step.saveMapping?.length || 0);
  const measureText = (text, font = '11px Inter') => {
    if (!text) return 0;
    if (!ctx) return text.length * 7;
    ctx.save();
    ctx.font = font;
    const width = ctx.measureText(text).width;
    ctx.restore();
    return width;
  };

  const maxInputLabelWidth = (step.inputs || []).reduce(
    (max, _, idx) => Math.max(max, measureText(getPortLabel(step, 'input', idx))),
    0,
  );
  const maxOutputLabelWidth = (step.saveMapping || []).reduce(
    (max, _, idx) => Math.max(max, measureText(getPortLabel(step, 'output', idx))),
    0,
  );
  const dynamicWidth = Math.ceil(maxInputLabelWidth + maxOutputLabelWidth + STEP_LABEL_PADDING);
  return {
    width: Math.max(STEP_MIN_WIDTH, dynamicWidth),
    height: STEP_BASE_HEIGHT + Math.max(0, portCount) * PORT_GAP,
  };
}

function getStepRect(step) {
  const { width, height } = getStepSize(step);
  return { x: step.x, y: step.y, width, height };
}

function getStepCenter(step) {
  const { width, height } = getStepSize(step);
  return { x: step.x + width / 2, y: step.y + height / 2 };
}

function getStepAnchor(step, side) {
  const { width, height } = getStepSize(step);
  if (side === 'input') {
    return { x: step.x, y: step.y + height / 2 };
  }
  return { x: step.x + width, y: step.y + height / 2 };
}

function getPortPosition(step, portType, index) {
  const count = portType === 'input' ? step.inputs?.length || 0 : step.saveMapping?.length || 0;
  if (index >= count) return null;
  const { width, height } = getStepSize(step);
  const availableHeight = height - 20;
  const y = step.y + 10 + ((index + 1) * availableHeight) / (count + 1);
  const x = portType === 'input' ? step.x : step.x + width;
  return { x, y };
}

function getPortLabel(step, portType, index) {
  if (portType === 'input') {
    const inp = step.inputs?.[index];
    return inp?.name || inp?.fromVar || `in ${index + 1}`;
  }
  const out = step.saveMapping?.[index];
  return out?.varName || out?.resultKey || `out ${index + 1}`;
}

function getAgentInputVarsList() {
  const vars = new Set([...(state.definitionInputVars || []), ...(state.runAgentKnownVars || [])]);
  Object.values(state.steps).forEach((step) => {
    (step.inputs || []).forEach((inp) => {
      const isAgentSource = !inp.fromStepId || inp.fromStepId === AGENT_INPUT_NODE_ID;
      if (!isAgentSource) return;
      const name = inp.fromVar || inp.name;
      if (name) vars.add(name);
    });
  });
  return Array.from(vars);
}

function getAgentOutputVarsList() {
  const vars = new Set();
  Object.values(state.steps).forEach((step) => {
    (step.saveMapping || []).forEach((m) => {
      if (m.varName) vars.add(m.varName);
      if (m.resultKey) vars.add(m.resultKey);
    });
  });
  return Array.from(vars);
}

function getRailPortLabel(side, index) {
  const collection = side === 'input' ? getAgentInputVarsList() : getAgentOutputVarsList();
  return collection[index] || '';
}

function getRailPortPosition(side, index) {
  if (!canvas) return null;
  const collection = side === 'input' ? getAgentInputVarsList() : getAgentOutputVarsList();
  if (index >= collection.length) return null;
  const availableHeight = Math.max(20, canvas.height - RAIL_PADDING * 2);
  const y = RAIL_PADDING + ((index + 1) * availableHeight) / (collection.length + 1);
  const x = side === 'input' ? RAIL_MARGIN : canvas.width - RAIL_MARGIN;
  return { x, y };
}

function findOutputIndexForVar(step, varName) {
  if (!varName) return -1;
  return (step.saveMapping || []).findIndex((m) => m.varName === varName || m.resultKey === varName);
}

function getPortAt(x, y) {
  for (const step of Object.values(state.steps)) {
    const inputCount = step.inputs?.length || 0;
    for (let i = 0; i < inputCount; i += 1) {
      const pos = getPortPosition(step, 'input', i);
      if (!pos) continue;
      const dist = Math.hypot(pos.x - x, pos.y - y);
      if (dist <= PORT_DETECTION_RADIUS) {
        return { kind: 'step', stepId: step.id, portType: 'input', index: i };
      }
    }

    const outputCount = step.saveMapping?.length || 0;
    for (let i = 0; i < outputCount; i += 1) {
      const pos = getPortPosition(step, 'output', i);
      if (!pos) continue;
      const dist = Math.hypot(pos.x - x, pos.y - y);
      if (dist <= PORT_DETECTION_RADIUS) {
        return { kind: 'step', stepId: step.id, portType: 'output', index: i };
      }
    }
  }

  const agentInputs = getAgentInputVarsList();
  for (let i = 0; i < agentInputs.length; i += 1) {
    const pos = getRailPortPosition('input', i);
    if (!pos) continue;
    const dist = Math.hypot(pos.x - x, pos.y - y);
    if (dist <= PORT_DETECTION_RADIUS) {
      return { kind: 'rail', rail: 'input', portType: 'output', index: i, label: agentInputs[i] };
    }
  }

  const agentOutputs = getAgentOutputVarsList();
  for (let i = 0; i < agentOutputs.length; i += 1) {
    const pos = getRailPortPosition('output', i);
    if (!pos) continue;
    const dist = Math.hypot(pos.x - x, pos.y - y);
    if (dist <= PORT_DETECTION_RADIUS) {
      return { kind: 'rail', rail: 'output', portType: 'input', index: i, label: agentOutputs[i] };
    }
  }
  return null;
}

async function fetchTools() {
  const res = await fetch('/api/tools');
  if (!res.ok) {
    setBanner('Не вдалося завантажити інструменти. Переконайтеся, що бекенд запущено.');
    return;
  }
  const data = await res.json();
  state.tools = data.tools || [];
  state.conditions = data.conditions || [];
  renderToolPalette();
}

async function fetchAgentsForRunPanel() {
  const select = document.getElementById('runAgentSelect');
  const statusEl = document.getElementById('runAgentStatus');
  if (!select) return;

  select.innerHTML = '<option value="">— оберіть агента —</option>';
  if (statusEl) statusEl.textContent = '';
  appendRunAgentLog('Завантаження списку агентів для запуску…');

  try {
    const res = await fetch('/api/agents');
    if (!res.ok) {
      if (statusEl) statusEl.textContent = 'Не вдалося завантажити агентів.';
      appendRunAgentLog('Не вдалося отримати список агентів', 'error', { status: res.status, statusText: res.statusText });
      return;
    }
    const data = await res.json();
    const agents = (data.agents || []).map(normalizeAgent).filter((a) => a.id);
    appendRunAgentLog('Отримано список агентів', 'info', agents);

    agents.forEach((agent, idx) => {
      const opt = document.createElement('option');
      opt.value = agent.id;
      opt.textContent = agent.name || agent.id;
      select.appendChild(opt);
    });

    if (agents.length) {
      select.value = agents[0].id;
      appendRunAgentLog('Автовибір першого агента для запуску', 'info', agents[0]);
      await loadRunAgentDetails(agents[0].id);
    }
  } catch (err) {
    console.error('Помилка завантаження агентів для запуску', err);
    appendRunAgentLog('Помилка завантаження агентів для запуску', 'error', err.message);
    if (statusEl) statusEl.textContent = 'Помилка завантаження агентів.';
  }
}

function extractAgentInputVars(definition = {}) {
  const vars = new Set();
  const schema = definition.input_schema;
  if (schema && typeof schema === 'object') {
    if (schema.properties && typeof schema.properties === 'object') {
      Object.keys(schema.properties).forEach((k) => vars.add(k));
    }
    if (Array.isArray(schema.required)) {
      schema.required.forEach((k) => vars.add(k));
    }
  }

  const steps = definition.steps || {};
  Object.values(steps).forEach((step = {}) => {
    const params = step.tool_params || {};
    Object.entries(params).forEach(([key, value]) => {
      if (typeof value !== 'string') return;
      if (key.endsWith('_var') || key.toLowerCase().includes('var')) {
        vars.add(value);
      }
      const matches = value.match(/\{([^{}]+)\}/g) || [];
      matches.forEach((m) => vars.add(m.replace(/\{|\}/g, '')));
    });
  });

  return Array.from(vars);
}

function renderRunAgentVarRows(varNames = []) {
  const container = document.getElementById('runAgentVars');
  if (!container) return;
  container.innerHTML = '';
  if (varNames.length) {
    varNames.forEach((name) => addRunAgentVarRow(name, '', 'known'));
  }
  addRunAgentVarRow('', '', 'custom');
}

async function loadRunAgentDetails(agentId) {
  const statusEl = document.getElementById('runAgentStatus');
  if (!agentId) {
    state.runAgentKnownVars = [];
    renderRunAgentVarRows([]);
    if (statusEl) statusEl.textContent = '';
    appendRunAgentLog('Агент не вибраний — очищено форму запуску', 'warn');
    return;
  }

  if (statusEl) statusEl.textContent = 'Завантаження вхідних змінних…';
  appendRunAgentLog('Завантаження опису агента', 'info', { agentId });

  try {
    const res = await fetch(`/api/agents/${encodeURIComponent(agentId)}`);
    if (!res.ok) {
      state.runAgentKnownVars = [];
      renderRunAgentVarRows([]);
      if (statusEl) statusEl.textContent = 'Не вдалося отримати опис агента.';
      appendRunAgentLog('Не вдалося отримати опис агента', 'error', { status: res.status, statusText: res.statusText });
      return;
    }
    const definition = await res.json();
    appendRunAgentLog('Отримано опис агента', 'info', definition);
    state.runAgentKnownVars = extractAgentInputVars(definition);
    appendRunAgentLog('Виявлені вхідні змінні', 'info', state.runAgentKnownVars);
    renderRunAgentVarRows(state.runAgentKnownVars);

    if (statusEl) {
      statusEl.textContent = state.runAgentKnownVars.length
        ? 'Вхідні змінні завантажено.'
        : 'Змінні не визначені, додайте власні.';
    }
  } catch (err) {
    console.error('Помилка завантаження опису агента', err);
    state.runAgentKnownVars = [];
    renderRunAgentVarRows([]);
    if (statusEl) statusEl.textContent = 'Помилка завантаження опису агента.';
  }
}

async function fetchAgents(autoLoadFirst = false) {
  const res = await fetch('/api/agents');
  if (!res.ok) {
    setBanner('Не вдалося отримати список агентів. Переконайтеся, що бекенд запущено.', 'info');
    if (!Object.keys(state.steps).length) {
      newAgent(true);
    }
    return;
  }
  const data = await res.json();
  state.agents = (data.agents || []).map(normalizeAgent).filter((a) => a.id);
  populateAgentOptions();
  renderAgentPalette();

  if (autoLoadFirst && state.agents.length) {
    await loadAgent(state.agents[0].id);
    document.getElementById('agentSelect').value = state.agents[0].id;
    document.getElementById('agentName').value = state.agents[0].id;
  } else if (!state.agents.length) {
    newAgent(true);
  }
  fetchAgentsGraph();
}

function renderToolPalette() {
  const palette = document.getElementById('toolPalette');
  if (!palette) {
    console.warn('toolPalette не знайдено');
    return;
  }
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

const NODE_TEMPLATES = [
  { kind: 'decision', label: 'Розгалуження', description: 'if/else на основі умов' },
  { kind: 'loop', label: 'Цикл', description: 'повторення з умовою виходу' },
  { kind: 'validator', label: 'Валідатор', description: 'перевірка результату' },
];

function renderAgentPalette() {
  const palette = document.getElementById('agentPalette');
  const filterInput = document.getElementById('agentPaletteFilter');
  if (!palette) return;

  const agents = filterAgents(state.agentPaletteFilter);
  palette.innerHTML = '';

  if (!agents.length && !NODE_TEMPLATES.length) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = 'Агентів не знайдено.';
    palette.appendChild(empty);
    return;
  }

  agents.forEach((agent) => {
    const pill = document.createElement('div');
    pill.className = 'tool-pill agent-pill';
    pill.draggable = true;
    pill.dataset.agent = agent.id;
    pill.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', `agent:${agent.id}`);
    });

    const title = document.createElement('strong');
    title.textContent = agent.name || agent.id;
    pill.appendChild(title);

    const desc = document.createElement('span');
    desc.className = 'muted';
    desc.textContent = agent.id;
    pill.appendChild(desc);

    palette.appendChild(pill);
  });

  const matchingNodes = NODE_TEMPLATES.filter(
    (tpl) =>
      !state.agentPaletteFilter ||
      tpl.label.toLowerCase().includes(state.agentPaletteFilter.toLowerCase()) ||
      tpl.kind.includes(state.agentPaletteFilter.toLowerCase()),
  );

  if (matchingNodes.length) {
    const header = document.createElement('div');
    header.className = 'muted palette-subheader';
    header.textContent = 'Спеціальні кроки';
    palette.appendChild(header);
  }

  matchingNodes.forEach((tpl) => {
    const pill = document.createElement('div');
    pill.className = 'tool-pill agent-pill';
    pill.draggable = true;
    pill.dataset.nodeKind = tpl.kind;
    pill.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', `node:${tpl.kind}`);
    });

    const title = document.createElement('strong');
    title.textContent = tpl.label;
    pill.appendChild(title);

    const desc = document.createElement('span');
    desc.className = 'muted';
    desc.textContent = tpl.description;
    pill.appendChild(desc);

    palette.appendChild(pill);
  });

  if (filterInput) {
    filterInput.value = state.agentPaletteFilter;
  }
}

  function populateToolAndConditionOptions() {
    const toolSelect = document.getElementById('toolName');
    const condSelect = document.getElementById('conditionType');

    if (!toolSelect && !condSelect) {
      console.warn('Форми для інструментів/умов не знайдено; пропускаємо заповнення.');
      return;
    }

    if (toolSelect) {
      toolSelect.innerHTML = '<option value="">—</option>';
      state.tools.forEach((tool) => {
        const opt = document.createElement('option');
        opt.value = tool.name || tool;
        opt.textContent = toolLabel(tool);
        opt.dataset.description = toolDescription(tool);
        toolSelect.appendChild(opt);
      });
    }

    if (condSelect) {
      condSelect.innerHTML = '';
      state.conditions.forEach((cond) => {
        const opt = document.createElement('option');
        opt.value = cond.type || cond;
        opt.textContent = cond.label_uk || cond.type;
        condSelect.appendChild(opt);
      });
      renderConditionFields(condSelect.value);
    }
  }

function renderConditionFields(selectedType) {
  const container = document.getElementById('conditionFields');
  if (!container) return;
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
  state.agents.forEach((agent) => {
    const opt = document.createElement('option');
    opt.value = agent.id;
    opt.textContent = agent.name || agent.id;
    select.appendChild(opt);
  });
}

function addStep(step) {
  if (!step.id) return;
  state.steps[step.id] = normalizeStep(step);
  refreshSelectors();
  render();
}

function deleteStep(stepId) {
  if (!state.steps[stepId]) return;

  delete state.steps[stepId];
  state.endStepIds.delete(stepId);

  Object.values(state.steps).forEach((step) => {
    (step.inputs || []).forEach((inp) => {
      if (inp.fromStepId === stepId) {
        inp.fromStepId = '';
      }
    });
    step.transitions = (step.transitions || []).filter((tr) => tr.targetStepId !== stepId);
  });

  if (state.entryStepId === stepId) {
    state.entryStepId = Object.keys(state.steps)[0] || '';
  }

  if (state.selectedStepId === stepId) {
    state.selectedStepId = null;
    const panel = document.getElementById('inspectorContent');
    if (panel) panel.textContent = t.selectStep;
  }

  refreshSelectors();
  renderAll();
}

function refreshSelectors() {
  const ids = Object.keys(state.steps);
  const entrySelect = document.getElementById('entryStep');
  const fromSelect = document.getElementById('fromStep');
  const toSelect = document.getElementById('toStep');
  const endStepsContainer = document.getElementById('endSteps');

  [entrySelect, fromSelect, toSelect]
    .filter(Boolean)
    .forEach((sel) => {
      sel.innerHTML = '';
      ids.forEach((id) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = id;
        sel.appendChild(opt);
      });
    });

  if (endStepsContainer) {
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
  }

  if (entrySelect) {
    if (state.entryStepId && ids.includes(state.entryStepId)) {
      entrySelect.value = state.entryStepId;
    } else if (ids.length && !state.entryStepId) {
      state.entryStepId = ids[0];
      entrySelect.value = state.entryStepId;
    }
  }
}

function getStepAt(x, y) {
  return Object.values(state.steps).find((step) => {
    const { width, height } = getStepSize(step);
    return x >= step.x && x <= step.x + width && y >= step.y && y <= step.y + height;
  });
}

function renderSaveMappingRows(step) {
  const container = document.getElementById('saveMappingRows');
  if (!container) return;
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
    const panel = document.getElementById('inspectorContent');
    if (panel) panel.textContent = t.selectStep;
    return;
  }
  renderInspector(step);
  render();
}

function renderInspector(step) {
  const panel = document.getElementById('inspectorContent');
  if (!panel) return;
  if (!step) {
    panel.textContent = t.selectStep;
    return;
  }

  panel.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'inspector-row title-row';
  header.innerHTML = `
    <div>
      <div class="muted">Ідентифікатор</div>
      <strong>${step.id}</strong>
    </div>
    <span class="badge">${step.kind || 'action'}</span>
  `;

  const nameField = document.createElement('div');
  nameField.className = 'field-group';
  nameField.innerHTML = '<label>Назва кроку</label>';
  const nameInput = document.createElement('input');
  nameInput.value = step.name || '';
  nameInput.placeholder = defaultNameFromKind(step.kind);
  nameInput.addEventListener('input', () => {
    step.name = nameInput.value;
    render();
    updatePreview();
  });
  nameField.appendChild(nameInput);

  const badgesRow = document.createElement('div');
  badgesRow.className = 'actions';
  const entryBtn = document.createElement('button');
  entryBtn.textContent = 'Зробити початковим';
  entryBtn.addEventListener('click', () => {
    state.entryStepId = step.id;
    document.getElementById('entryStep').value = step.id;
    renderAll();
  });
  const endBtn = document.createElement('button');
  endBtn.textContent = state.endStepIds.has(step.id) ? 'Прибрати завершальний' : 'Позначити завершальним';
  endBtn.addEventListener('click', () => {
    if (state.endStepIds.has(step.id)) {
      state.endStepIds.delete(step.id);
    } else {
      state.endStepIds.add(step.id);
    }
    refreshSelectors();
    renderAll();
  });
  badgesRow.append(entryBtn, endBtn);

  const inputsSection = document.createElement('div');
  inputsSection.className = 'inspector-block';
  inputsSection.innerHTML = '<h3>Вхідні параметри</h3><p class="muted">Змінні, які крок читає перед виконанням.</p>';
  const inputsContainer = document.createElement('div');
  inputsContainer.className = 'table-list';

  const renderInputs = () => {
    inputsContainer.innerHTML = '';
    (step.inputs || []).forEach((inp, idx) => {
      const row = document.createElement('div');
      row.className = 'table-row';

      const name = document.createElement('input');
      name.placeholder = 'Ім’я змінної';
      name.value = inp.name || '';
      name.addEventListener('input', () => {
        step.inputs[idx].name = name.value;
        updatePreview();
        render();
      });

      const from = document.createElement('input');
      from.placeholder = 'Брати зі змінної агента';
      from.value = inp.fromVar || '';
      from.addEventListener('input', () => {
        step.inputs[idx].fromVar = from.value;
        updatePreview();
        render();
      });

      const def = document.createElement('input');
      def.placeholder = 'Значення за замовчуванням';
      def.value = inp.defaultValue ?? '';
      def.addEventListener('input', () => {
        step.inputs[idx].defaultValue = def.value;
        updatePreview();
      });

      const desc = document.createElement('input');
      desc.placeholder = 'Опис';
      desc.value = inp.description || '';
      desc.addEventListener('input', () => {
        step.inputs[idx].description = desc.value;
        updatePreview();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '✕';
      remove.addEventListener('click', () => {
        step.inputs.splice(idx, 1);
        renderInputs();
        updatePreview();
        render();
      });

      row.append(name, from, def, desc, remove);
      inputsContainer.appendChild(row);
    });
    if (!step.inputs || !step.inputs.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Додайте параметри, які читає крок.';
      inputsContainer.appendChild(empty);
    }
  };
  renderInputs();

  const addInputBtn = document.createElement('button');
  addInputBtn.type = 'button';
  addInputBtn.textContent = '+ Додати параметр';
  addInputBtn.addEventListener('click', () => {
    step.inputs = step.inputs || [];
    step.inputs.push({ name: '', fromVar: '', fromStepId: '', defaultValue: '', description: '' });
    renderInputs();
    updatePreview();
    render();
  });
  inputsSection.append(inputsContainer, addInputBtn);

  const bodySection = document.createElement('div');
  bodySection.className = 'inspector-block';
  bodySection.innerHTML = '<h3>Тіло кроку</h3><p class="muted">Оберіть атомарний інструмент та його параметри.</p>';

  const toolSelect = document.createElement('select');
  const emptyOpt = document.createElement('option');
  emptyOpt.value = '';
  emptyOpt.textContent = '— Оберіть інструмент —';
  toolSelect.appendChild(emptyOpt);
  state.tools.forEach((tool) => {
    const opt = document.createElement('option');
    opt.value = tool.name || tool;
    opt.textContent = toolLabel(tool);
    opt.title = toolDescription(tool);
    toolSelect.appendChild(opt);
  });
  toolSelect.value = step.toolName || '';

  const toolDesc = document.createElement('p');
  toolDesc.className = 'muted';
  const updateToolInfo = () => {
    const meta = state.tools.find((t) => t.name === toolSelect.value);
    toolDesc.textContent = toolDescription(meta) || 'Оберіть інструмент для налаштування.';
  };
  updateToolInfo();

  const paramsWrapper = document.createElement('div');
  paramsWrapper.className = 'field-group';

  function renderToolParams() {
    paramsWrapper.innerHTML = '';
    const meta = state.tools.find((t) => t.name === step.toolName) || {};
    const schema = meta.schema || {};
    const props = schema.properties || null;
    const params = Array.isArray(schema.params) ? schema.params : null;

    if (step.toolName === 'agent_call') {
      const agentSelectWrap = document.createElement('div');
      agentSelectWrap.className = 'field-group';
      const agentLabel = document.createElement('label');
      agentLabel.textContent = 'Цільовий агент';
      const agentSelect = document.createElement('select');
      agentSelect.innerHTML = '<option value="">— оберіть агента —</option>';
      state.agents.forEach((agent) => {
        const opt = document.createElement('option');
        opt.value = agent.id;
        opt.textContent = agent.name || agent.id;
        agentSelect.appendChild(opt);
      });
      agentSelect.value = step.toolParams?.agent_name || '';
      agentSelect.addEventListener('change', () => {
        step.toolParams = step.toolParams || {};
        step.toolParams.agent_name = agentSelect.value;
        updatePreview();
      });
      agentSelectWrap.append(agentLabel, agentSelect);
      paramsWrapper.appendChild(agentSelectWrap);

      const hint = document.createElement('p');
      hint.className = 'muted';
      hint.textContent = 'Перетягніть агента з палітри ліворуч або виберіть зі списку.';
      paramsWrapper.appendChild(hint);
    }

    if (params) {
      params.forEach((cfg) => {
        const key = cfg.name;
        const wrapper = document.createElement('div');
        wrapper.className = 'field-group';
        const label = document.createElement('label');
        label.textContent = cfg.title || cfg.label_uk || key;
        const input = document.createElement(cfg.type === 'boolean' ? 'input' : 'textarea');
        if (cfg.type === 'boolean') {
          input.type = 'checkbox';
          input.checked = Boolean(step.toolParams?.[key]);
          input.addEventListener('change', () => {
            step.toolParams = step.toolParams || {};
            step.toolParams[key] = input.checked;
            updatePreview();
          });
        } else {
          input.rows = 2;
          input.value = step.toolParams?.[key] ?? '';
          input.placeholder = cfg.description_uk || cfg.description || '';
          input.addEventListener('input', () => {
            step.toolParams = step.toolParams || {};
            step.toolParams[key] = input.value;
            updatePreview();
          });
        }
        wrapper.append(label, input);
        paramsWrapper.appendChild(wrapper);
      });
      return;
    }

    if (props) {
      Object.entries(props).forEach(([key, cfg]) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'field-group';
        const label = document.createElement('label');
        label.textContent = cfg.title || cfg.label_uk || key;
        const inputType = cfg.type === 'boolean' ? 'checkbox' : 'input';
        let input;
        if (inputType === 'checkbox') {
          input = document.createElement('input');
          input.type = 'checkbox';
          input.checked = Boolean(step.toolParams?.[key]);
          input.addEventListener('change', () => {
            step.toolParams = step.toolParams || {};
            step.toolParams[key] = input.checked;
            updatePreview();
          });
        } else {
          input = document.createElement('textarea');
          input.rows = 2;
          input.value = step.toolParams?.[key] ?? '';
          input.placeholder = cfg.description_uk || cfg.description || '';
          input.addEventListener('input', () => {
            step.toolParams = step.toolParams || {};
            step.toolParams[key] = input.value;
            updatePreview();
          });
        }
        wrapper.append(label, input);
        paramsWrapper.appendChild(wrapper);
      });
      return;
    }

    const label = document.createElement('label');
    label.textContent = 'Сирі параметри (JSON)';
    const textarea = document.createElement('textarea');
    textarea.rows = 4;
    textarea.value = JSON.stringify(step.toolParams || {}, null, 2);
    textarea.addEventListener('input', () => {
      try {
        step.toolParams = JSON.parse(textarea.value || '{}');
        textarea.classList.remove('error');
        updatePreview();
      } catch (err) {
        textarea.classList.add('error');
      }
    });
    paramsWrapper.append(label, textarea);
  }

  toolSelect.addEventListener('change', () => {
    step.toolName = toolSelect.value || null;
    updateToolInfo();
    renderToolParams();
    updatePreview();
  });

  bodySection.append(toolSelect, toolDesc, paramsWrapper);
  renderToolParams();

  const outputsSection = document.createElement('div');
  outputsSection.className = 'inspector-block';
  outputsSection.innerHTML = '<h3>Вихідні параметри</h3><p class="muted">Куди записати результати інструмента.</p>';
  const outputsContainer = document.createElement('div');
  outputsContainer.className = 'table-list';

  const renderOutputs = () => {
    outputsContainer.innerHTML = '';
    (step.saveMapping || []).forEach((m, idx) => {
      const row = document.createElement('div');
      row.className = 'table-row';

      const resultInput = document.createElement('input');
      resultInput.placeholder = 'Поле результату (наприклад parsed_json.decision)';
      resultInput.value = m.resultKey || '';
      resultInput.addEventListener('input', () => {
        step.saveMapping[idx].resultKey = resultInput.value;
        updatePreview();
        render();
      });

      const varInput = document.createElement('input');
      varInput.placeholder = 'Записати в змінну агента';
      varInput.value = m.varName || '';
      varInput.addEventListener('input', () => {
        step.saveMapping[idx].varName = varInput.value;
        updatePreview();
        render();
      });

      const descInput = document.createElement('input');
      descInput.placeholder = 'Опис';
      descInput.value = m.description || '';
      descInput.addEventListener('input', () => {
        step.saveMapping[idx].description = descInput.value;
        updatePreview();
        render();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '✕';
      remove.addEventListener('click', () => {
        step.saveMapping.splice(idx, 1);
        renderOutputs();
        updatePreview();
        render();
      });

      row.append(resultInput, varInput, descInput, remove);
      outputsContainer.appendChild(row);
    });
    if (!step.saveMapping || !step.saveMapping.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Додайте принаймні один вихід для збереження результату.';
      outputsContainer.appendChild(empty);
    }
  };
  renderOutputs();

  const addOutputBtn = document.createElement('button');
  addOutputBtn.type = 'button';
  addOutputBtn.textContent = '+ Додати вихід';
  addOutputBtn.addEventListener('click', () => {
    step.saveMapping = step.saveMapping || [];
    step.saveMapping.push({ resultKey: '', varName: '', description: '' });
    renderOutputs();
    updatePreview();
    render();
  });
  outputsSection.append(outputsContainer, addOutputBtn);

  const transitionsSection = document.createElement('div');
  transitionsSection.className = 'inspector-block';
  transitionsSection.innerHTML = `<h3>Переходи (розгалуження / цикл)</h3>
    <p class="muted">${
      step.kind === 'decision'
        ? 'Додайте щонайменше дві гілки з умовами для if/else.'
        : step.kind === 'loop'
          ? 'Перша гілка спрямована на себе. Додайте умову виходу з циклу.'
          : 'Опишіть, куди переходить виконання після кроку.'
    }</p>`;
  const trContainer = document.createElement('div');
  trContainer.className = 'table-list';

  const renderTransitions = () => {
    trContainer.innerHTML = '';
    (step.transitions || []).forEach((tr, idx) => {
      const row = document.createElement('div');
      row.className = 'table-row';

      const targetSelect = document.createElement('select');
      Object.keys(state.steps).forEach((id) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = id;
        targetSelect.appendChild(opt);
      });
      targetSelect.value = tr.targetStepId || '';
      targetSelect.addEventListener('change', () => {
        tr.targetStepId = targetSelect.value;
        render();
        updatePreview();
      });

      const condSelect = document.createElement('select');
      state.conditions.forEach((cond) => {
        const opt = document.createElement('option');
        opt.value = cond.type;
        opt.textContent = cond.label_uk || cond.type;
        condSelect.appendChild(opt);
      });
      condSelect.value = tr.condition?.type || 'always';

      const fieldsWrapper = document.createElement('div');
      fieldsWrapper.className = 'transition-fields';

      const renderFields = () => {
        fieldsWrapper.innerHTML = '';
        const meta = getConditionMeta(condSelect.value) || { fields: [] };
        (meta.fields || []).forEach((f) => {
          const input = document.createElement('input');
          input.placeholder = f.label_uk || f.name;
          input.value = tr.condition?.params?.[f.name] ?? '';
          input.addEventListener('input', () => {
            tr.condition = tr.condition || { type: condSelect.value, params: {} };
            tr.condition.params = tr.condition.params || {};
            tr.condition.params[f.name] = input.value;
            updatePreview();
          });
          fieldsWrapper.appendChild(input);
        });
      };
      renderFields();

      condSelect.addEventListener('change', () => {
        tr.condition = { type: condSelect.value, params: {} };
        renderFields();
        render();
        updatePreview();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Видалити';
      remove.addEventListener('click', () => {
        step.transitions.splice(idx, 1);
        renderTransitions();
        render();
        updatePreview();
      });

      row.append(targetSelect, condSelect, fieldsWrapper, remove);
      trContainer.appendChild(row);
    });

    if (!step.transitions || !step.transitions.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Додайте перехід, щоб визначити наступний крок.';
      trContainer.appendChild(empty);
    }
  };
  renderTransitions();

  const addTransitionBtn = document.createElement('button');
  addTransitionBtn.type = 'button';
  addTransitionBtn.textContent = '+ Додати перехід';
  addTransitionBtn.addEventListener('click', () => {
    const firstId = Object.keys(state.steps)[0];
    step.transitions = step.transitions || [];
    step.transitions.push({
      id: generateTransitionId(),
      targetStepId: firstId || step.id,
      condition: { type: 'always', params: {} },
    });
    renderTransitions();
    updatePreview();
  });
  transitionsSection.append(trContainer, addTransitionBtn);

  panel.append(header, nameField, badgesRow, inputsSection, bodySection, outputsSection, transitionsSection);
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
    const saveMapping = {};
    (step.saveMapping || []).forEach((m) => {
      if (m.varName && m.resultKey) saveMapping[m.varName] = m.resultKey;
    });
    const inputs = (step.inputs || []).map((inp) => ({
      name: inp.name,
      fromVar: inp.fromVar,
      from_step_id: inp.fromStepId,
      defaultValue: inp.defaultValue,
      description: inp.description,
    }));
    const inputLinks = (step.inputs || [])
      .map((inp, idx) =>
        inp.fromStepId
          ? {
              input: inp.name || `input_${idx + 1}`,
              input_index: idx,
              from_step_id: inp.fromStepId,
              from_var: inp.fromVar,
            }
          : null,
      )
      .filter(Boolean);
    const transitions = (step.transitions || []).map((tr) => {
      const condition = tr.condition || {};
      const params = condition.params || {};
      const conditionPayload = { type: condition.type || 'always', ...params };
      return {
        id: tr.id,
        target_step_id: tr.targetStepId,
        condition: conditionPayload,
      };
    });
    stepsPayload[step.id] = {
      name: step.name,
      kind: step.kind,
      tool_name: step.toolName,
      tool_params: step.toolParams || {},
      inputs,
      input_links: inputLinks,
      save_mapping: saveMapping,
      validator_agent_name: step.validatorAgentName,
      validator_params: step.validatorParams || {},
      validator_policy: step.validatorPolicy || {},
      transitions,
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

function ensureTransition(fromStep, targetStepId) {
  fromStep.transitions = fromStep.transitions || [];
  const existing = fromStep.transitions.find((tr) => tr.targetStepId === targetStepId);
  if (existing) return existing;
  const created = {
    id: generateTransitionId(),
    targetStepId,
    condition: { type: 'always', params: {} },
  };
  fromStep.transitions.push(created);
  refreshSelectors();
  return created;
}

function connectOutputToInput(sourceStepId, outputIndex, targetStepId, inputIndex) {
  const source = state.steps[sourceStepId];
  const target = state.steps[targetStepId];
  if (!source || !target) return;
  const output = source.saveMapping?.[outputIndex];
  const input = target.inputs?.[inputIndex];
  if (!output || !input) return;

  const inferredVar = output.varName || output.resultKey || input.name || `out_${outputIndex + 1}`;
  if (!output.varName) output.varName = inferredVar;
  input.fromVar = inferredVar;
  input.fromStepId = sourceStepId;

  ensureTransition(source, targetStepId);

  if (state.selectedStepId === targetStepId) {
    renderInspector(target);
  } else if (state.selectedStepId === sourceStepId) {
    renderInspector(source);
  }
  updatePreview();
  render();
}

function connectAgentInputToStepInput(agentInputIndex, targetStepId, inputIndex) {
  const target = state.steps[targetStepId];
  if (!target) return;
  const input = target.inputs?.[inputIndex];
  if (!input) return;
  const label = getRailPortLabel('input', agentInputIndex) || input.name || `input_${agentInputIndex + 1}`;
  input.fromVar = label;
  input.fromStepId = AGENT_INPUT_NODE_ID;
  if (state.selectedStepId === targetStepId) {
    renderInspector(target);
  }
  updatePreview();
  render();
}

function connectStepOutputToAgentOutput(sourceStepId, outputIndex, agentOutputIndex) {
  const source = state.steps[sourceStepId];
  if (!source) return;
  const output = source.saveMapping?.[outputIndex];
  if (!output) return;
  const label = getRailPortLabel('output', agentOutputIndex) || output.varName || output.resultKey || `out_${outputIndex + 1}`;
  if (!output.varName) output.varName = label;
  if (!output.resultKey) output.resultKey = label;
  if (state.selectedStepId === sourceStepId) {
    renderInspector(source);
  }
  updatePreview();
  render();
}

function resolveLinkStart(link) {
  if (!link) return null;
  if (link.fromKind === 'rail') {
    const pos = getRailPortPosition(link.rail, link.fromPortIndex);
    return pos || null;
  }
  const source = state.steps[link.from];
  if (!source) return null;
  if (link.fromPortType === 'output' && link.fromPortIndex >= 0) {
    return getPortPosition(source, 'output', link.fromPortIndex) || getStepAnchor(source, 'output');
  }
  return getStepAnchor(source, 'output');
}

function drawArrow(start, end, options = {}) {
  const { color = '#1d5dff', dashed = false, label } = options;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  if (dashed) ctx.setLineDash([6, 4]);

  ctx.beginPath();
  const isLoop = start.x === end.x && start.y === end.y;
  let arrowEnd = { ...end };
  if (isLoop) {
    const cp1 = { x: start.x + 50, y: start.y - 60 };
    const cp2 = { x: start.x - 50, y: start.y - 60 };
    arrowEnd = { x: start.x, y: start.y - 30 };
    ctx.moveTo(start.x, start.y);
    ctx.bezierCurveTo(cp1.x, cp1.y, cp2.x, cp2.y, arrowEnd.x, arrowEnd.y);
  } else {
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  const angle = Math.atan2(arrowEnd.y - start.y, arrowEnd.x - start.x);
  ctx.beginPath();
  ctx.moveTo(arrowEnd.x, arrowEnd.y);
  ctx.lineTo(arrowEnd.x - 8 * Math.cos(angle - Math.PI / 6), arrowEnd.y - 8 * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(arrowEnd.x - 8 * Math.cos(angle + Math.PI / 6), arrowEnd.y - 8 * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();

  if (label) {
    const midX = isLoop ? start.x + 4 : (start.x + end.x) / 2;
    const midY = isLoop ? start.y - 50 : (start.y + end.y) / 2;
    ctx.fillStyle = 'rgba(13, 27, 42, 0.7)';
    ctx.font = '11px Inter';
    ctx.fillText(label, midX + 4, midY - 4);
  }
  ctx.restore();
}

function renderStepOverlays() {
  const overlay = document.getElementById('canvasOverlay');
  if (!overlay || !canvas) return;

  overlay.style.left = `${canvas.offsetLeft}px`;
  overlay.style.top = `${canvas.offsetTop}px`;
  overlay.style.width = `${canvas.clientWidth}px`;
  overlay.style.height = `${canvas.clientHeight}px`;
  overlay.innerHTML = '';

  Object.values(state.steps).forEach((step) => {
    const { width } = getStepSize(step);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'step-delete-btn';
    btn.title = 'Видалити крок';
    btn.setAttribute('aria-label', `Видалити крок ${step.name || step.id}`);
    btn.style.left = `${step.x + width - 18}px`;
    btn.style.top = `${step.y + 6}px`;
    btn.textContent = '✕';
    btn.addEventListener('click', (event) => {
      event.stopPropagation();
      deleteStep(step.id);
    });
    btn.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        deleteStep(step.id);
      }
    });
    overlay.appendChild(btn);
  });
}

function render() {
  if (!canvas || !ctx) return;
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

  const agentInputs = getAgentInputVarsList();
  const agentOutputs = getAgentOutputVarsList();

  ctx.save();
  ctx.strokeStyle = '#9aa9c1';
  ctx.lineWidth = 1.5;
  if (agentInputs.length) {
    ctx.beginPath();
    ctx.moveTo(RAIL_MARGIN, 8);
    ctx.lineTo(RAIL_MARGIN, canvas.height - 8);
    ctx.stroke();
  }
  if (agentOutputs.length) {
    ctx.beginPath();
    ctx.moveTo(canvas.width - RAIL_MARGIN, 8);
    ctx.lineTo(canvas.width - RAIL_MARGIN, canvas.height - 8);
    ctx.stroke();
  }
  ctx.font = '11px Inter';
  agentInputs.forEach((name, idx) => {
    const pos = getRailPortPosition('input', idx);
    if (!pos) return;
    ctx.fillStyle = '#1d3557';
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, PORT_RADIUS, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0d1b2a';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(name || `input_${idx + 1}`, pos.x + PORT_RADIUS + 4, pos.y);
  });
  agentOutputs.forEach((name, idx) => {
    const pos = getRailPortPosition('output', idx);
    if (!pos) return;
    ctx.fillStyle = '#1d3557';
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, PORT_RADIUS, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0d1b2a';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(name || `output_${idx + 1}`, pos.x - PORT_RADIUS - 4, pos.y);
  });
  ctx.restore();

  const connectedPairs = new Set();

  Object.values(state.steps).forEach((step) => {
    (step.inputs || []).forEach((inp, idx) => {
      const label = inp.fromVar || inp.name || '';
      const fromAgentRail =
        inp.fromStepId === AGENT_INPUT_NODE_ID ||
        (!inp.fromStepId && label && agentInputs.includes(label));
      if (fromAgentRail) {
        const portIdx = label ? agentInputs.indexOf(label) : -1;
        const start =
          portIdx >= 0
            ? getRailPortPosition('input', portIdx)
            : { x: RAIL_MARGIN, y: getPortPosition(step, 'input', idx)?.y || step.y };
        const end = getPortPosition(step, 'input', idx) || getStepAnchor(step, 'input');
        drawArrow(start || { x: RAIL_MARGIN, y: end?.y || 0 }, end, { label });
        return;
      }

      if (!inp.fromStepId) return;
      const source = state.steps[inp.fromStepId];
      if (!source) return;
      const outputIdx = findOutputIndexForVar(source, inp.fromVar);
      const start =
        outputIdx >= 0 ? getPortPosition(source, 'output', outputIdx) : getStepAnchor(source, 'output');
      const end = getPortPosition(step, 'input', idx) || getStepAnchor(step, 'input');
      drawArrow(start || getStepAnchor(source, 'output'), end, { label });
      connectedPairs.add(`${source.id}->${step.id}`);
    });
  });

  Object.values(state.steps).forEach((step) => {
    (step.saveMapping || []).forEach((m, idx) => {
      const label = m.varName || m.resultKey || '';
      if (!label) return;
      const portIdx = agentOutputs.indexOf(label);
      if (portIdx < 0) return;
      const start = getPortPosition(step, 'output', idx) || getStepAnchor(step, 'output');
      const end =
        getRailPortPosition('output', portIdx) || { x: canvas.width - RAIL_MARGIN, y: start?.y || 0 };
      drawArrow(start, end, { label });
    });
  });

  Object.values(state.steps).forEach((step) => {
    (step.transitions || []).forEach((tr) => {
      const target = state.steps[tr.targetStepId];
      if (!target) return;
      const linkedInputIndex = (target.inputs || []).findIndex((inp) => inp.fromStepId === step.id);
      const linkedOutputIndex =
        linkedInputIndex >= 0
          ? findOutputIndexForVar(step, target.inputs[linkedInputIndex].fromVar)
          : -1;
      const start =
        linkedOutputIndex >= 0
          ? getPortPosition(step, 'output', linkedOutputIndex)
          : getStepAnchor(step, 'output');
      const end =
        linkedInputIndex >= 0
          ? getPortPosition(target, 'input', linkedInputIndex)
          : step.id === target.id
            ? start
            : getStepAnchor(target, 'input');
      const meta = getConditionMeta(tr.condition?.type);
      const label = meta?.label_uk || tr.condition?.type;
      const color = connectedPairs.has(`${step.id}->${target.id}`) ? '#9aa9c1' : '#1d5dff';
      drawArrow(start || getStepAnchor(step, 'output'), end || getStepAnchor(target, 'input'), {
        label,
        color,
      });
    });
  });

  if (state.draggingLink) {
    const fromPoint = resolveLinkStart(state.draggingLink);
    if (fromPoint) {
      drawArrow(fromPoint, { x: state.draggingLink.x, y: state.draggingLink.y }, {
        color: '#f39c12',
        dashed: true,
      });
    }
  }

  Object.values(state.steps).forEach((step) => {
    const { width, height } = getStepSize(step);
    ctx.fillStyle = state.selectedStepId === step.id ? '#e6f0ff' : '#fff';
    ctx.strokeStyle = '#1d3557';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(step.x, step.y, width, height, 8);
    } else {
      ctx.rect(step.x, step.y, width, height);
    }
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#0d1b2a';
    ctx.font = 'bold 13px Inter';
    ctx.fillText(step.name || step.id, step.x + 10, step.y + 20);
    ctx.font = '12px Inter';
    const meta = state.tools.find((t) => t.name === step.toolName);
    const label = meta ? toolLabel(meta) : step.toolName || '';
    ctx.fillText(label, step.x + 10, step.y + 38);

    ctx.save();
    ctx.font = '11px Inter';
    (step.inputs || []).forEach((inp, idx) => {
      const pos = getPortPosition(step, 'input', idx);
      if (!pos) return;
      ctx.fillStyle = '#1d3557';
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, PORT_RADIUS, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#0d1b2a';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(getPortLabel(step, 'input', idx), pos.x + PORT_RADIUS + 4, pos.y);
    });

    (step.saveMapping || []).forEach((m, idx) => {
      const pos = getPortPosition(step, 'output', idx);
      if (!pos) return;
      ctx.fillStyle = '#1d3557';
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, PORT_RADIUS, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#0d1b2a';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(getPortLabel(step, 'output', idx), pos.x - PORT_RADIUS - 4, pos.y);
    });
    ctx.restore();
  });

  renderStepOverlays();
}

function startDrag(event) {
  const { offsetX, offsetY } = event;
  const portHit = getPortAt(offsetX, offsetY);
  if (portHit?.portType === 'output') {
    state.draggingLink = {
      from: portHit.stepId || null,
      fromKind: portHit.kind || 'step',
      rail: portHit.rail,
      fromLabel: portHit.label,
      fromPortType: portHit.portType,
      fromPortIndex: portHit.index,
      x: offsetX,
      y: offsetY,
    };
    return;
  }
  const hit = getStepAt(offsetX, offsetY);
  if (hit && event.shiftKey) {
    state.draggingLink = { from: hit.id, fromKind: 'step', fromPortType: 'step', x: offsetX, y: offsetY };
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
  state.definitionInputVars = extractAgentInputVars(def);
  state.selectedStepId = null;
  Object.entries(def.steps || {}).forEach(([id, step]) => {
    addStep({ id, ...step });
  });
  state.transitionCounter =
    Object.values(state.steps).reduce((acc, s) => acc + (s.transitions?.length || 0), 0) + 1;
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
  state.definitionInputVars = [];
  state.selectedStepId = null;
  withElement('agentName', (el) => {
    el.value = 'new_agent';
  });
  withElement('agentSelect', (el) => {
    el.value = '';
  });
  withElement('inspectorContent', (el) => {
    el.textContent = t.selectStep;
  });
  if (seed) {
    const tool = state.tools[0]?.name || state.tools[0];
    const id = 'init';
    addStep({ id, name: 'Початковий крок', kind: 'action', toolName: tool });
    state.entryStepId = id;
    withElement('entryStep', (el) => {
      el.value = id;
    });
    selectStep(id);
  }
  refreshSelectors();
  updatePreview();
  render();
}

function addTransition(evt) {
  evt.preventDefault();
  const fromEl = document.getElementById('fromStep');
  const toEl = document.getElementById('toStep');
  const typeEl = document.getElementById('conditionType');
  const fieldContainer = document.getElementById('conditionFields');
  if (!fromEl || !toEl || !typeEl) return;
  const from = fromEl.value;
  const to = toEl.value;
  if (!from || !to) return;
  const type = typeEl.value;
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
  const payload = evt.dataTransfer.getData('text/plain');
  if (!payload) return;
  const rect = canvas.getBoundingClientRect();
  const { width } = getStepSize({ inputs: [], saveMapping: [] });
  const x = evt.clientX - rect.left - width / 2;
  const y = evt.clientY - rect.top - STEP_BASE_HEIGHT / 2;
  const agentMatch = payload.startsWith('agent:') ? payload.slice('agent:'.length) : null;
  if (agentMatch) {
    const agent = state.agents.find((a) => a.id === agentMatch);
    createStep('action', {
      name: agent?.name || agentMatch,
      toolName: 'agent_call',
      toolParams: { agent_name: agentMatch },
      x,
      y,
    });
    updatePreview();
    return;
  }

  const nodeMatch = payload.startsWith('node:') ? payload.slice('node:'.length) : null;
  if (nodeMatch) {
    createStep(nodeMatch, { x, y });
    updatePreview();
    return;
  }

  createStep('action', { toolName: payload, x, y });
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

async function runSelectedAgent() {
  const select = document.getElementById('runAgentSelect');
  const outputEl = document.getElementById('runAgentOutput');
  const statusEl = document.getElementById('runAgentStatus');

  if (!select || !outputEl) return;
  clearRunAgentLog();
  const agentId = select.value;
  if (!agentId) {
    if (statusEl) statusEl.textContent = 'Оберіть агента для запуску.';
    outputEl.textContent = '';
    appendRunAgentLog('Запуск скасовано: агент не вибраний', 'warn');
    return;
  }

  const payload = collectRunAgentInput();
  appendRunAgentLog('Запуск агента', 'info', { agent_id: agentId, input_json: payload });

  if (statusEl) statusEl.textContent = 'Виконується…';
  outputEl.textContent = '';

  try {
    const res = await fetch('/api/agents/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId, input_json: payload }),
    });
    appendRunAgentLog('Отримано відповідь', 'info', { status: res.status, statusText: res.statusText });
    const rawText = await res.text();
    appendRunAgentLog('Сире тіло відповіді', res.ok ? 'info' : 'warn', rawText || '[порожньо]');
    let data = {};
    try {
      data = rawText ? JSON.parse(rawText) : {};
    } catch (parseErr) {
      console.error('[Запуск агента] Не вдалося розпарсити відповідь як JSON', parseErr, rawText);
      appendRunAgentLog('Не вдалося розпарсити JSON відповіді', 'error', parseErr.message);
      data = { raw: rawText };
    }

    appendRunAgentLog('Розібране тіло відповіді', res.ok ? 'info' : 'warn', data);

    if (!res.ok) {
      if (statusEl) statusEl.textContent = 'Помилка';
      outputEl.textContent = data.error || res.statusText || rawText || 'Невідома помилка запуску.';
      appendRunAgentLog('Запуск завершився HTTP-помилкою', 'error', outputEl.textContent);
      return;
    }

    if (data.failed || data.ok === false) {
      if (statusEl) statusEl.textContent = `Помилка: ${data.error || 'невідомо чому'}`;
      outputEl.textContent = JSON.stringify(data, null, 2);
      appendRunAgentLog('Агент повідомив про помилку', 'error', data);
      return;
    }

    if (statusEl) statusEl.textContent = 'Успіх';
    outputEl.textContent = JSON.stringify(data, null, 2);
    appendRunAgentLog('Запуск успішний', 'info', data);
  } catch (err) {
    console.error('[Запуск агента] Помилка виконання запиту', err);
    appendRunAgentLog('Помилка виконання запиту', 'error', err.message);
    if (statusEl) statusEl.textContent = `Помилка: ${err.message}`;
    outputEl.textContent = err.message;
  }
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

function renderAll() {
  render();
  updatePreview();
  if (state.selectedStepId) {
    renderInspector(state.steps[state.selectedStepId]);
  }
}

function registerEventHandlers() {
  withElement('saveAgent', (el) => el.addEventListener('click', saveAgent));
  withElement('validateAgent', (el) => el.addEventListener('click', validateAgent));
  withElement('loadAgent', (el) => el.addEventListener('click', loadAgent));
  withElement('newAgent', (el) => el.addEventListener('click', newAgent));
  withElement('refreshAgents', (el) => el.addEventListener('click', () => fetchAgents()));
  withElement('agentPaletteFilter', (el) =>
    el.addEventListener('input', (e) => {
      state.agentPaletteFilter = e.target.value;
      renderAgentPalette();
    }),
  );
  withElement('addActionStep', (el) => el.addEventListener('click', () => createStep('action')));
  withElement('addDecisionStep', (el) => el.addEventListener('click', () => createStep('decision')));
  withElement('addLoopStep', (el) => el.addEventListener('click', () => createStep('loop')));
  withElement('addValidatorStep', (el) => el.addEventListener('click', () => createStep('validator')));
  withElement('agentSelect', (el) => {
    el.addEventListener('change', (e) => {
      withElement('agentName', (nameEl) => {
        nameEl.value = e.target.value;
      });
    });
  });
  withElement('entryStep', (el) => {
    el.addEventListener('change', (e) => {
      state.entryStepId = e.target.value;
      render();
      updatePreview();
    });
  });
  withElement('importJson', (el) => el.addEventListener('click', importJson));
  withElement('exportJson', (el) => el.addEventListener('click', exportJson));
  withElement('runAgentBtn', (el) => el.addEventListener('click', runSelectedAgent));
  withElement('runAgentSelect', (el) => el.addEventListener('change', (e) => loadRunAgentDetails(e.target.value)));
  withElement('addRunAgentVar', (el) => el.addEventListener('click', () => addRunAgentVarRow()));

  if (canvas) {
    canvas.addEventListener('mousedown', startDrag);
    canvas.addEventListener('mousemove', onDrag);
    canvas.addEventListener('mouseup', (event) => {
      if (state.draggingLink) {
        const portHit = getPortAt(event.offsetX, event.offsetY);
        const link = state.draggingLink;
        if (link.fromKind === 'rail' && link.rail === 'input' && portHit?.kind === 'step' && portHit.portType === 'input') {
          connectAgentInputToStepInput(link.fromPortIndex, portHit.stepId, portHit.index);
        } else if (
          link.fromKind === 'step' &&
          link.fromPortType === 'output' &&
          portHit?.kind === 'step' &&
          portHit.portType === 'input'
        ) {
          connectOutputToInput(
            link.from,
            link.fromPortIndex,
            portHit.stepId,
            portHit.index,
          );
        } else if (
          link.fromKind === 'step' &&
          link.fromPortType === 'output' &&
          portHit?.kind === 'rail' &&
          portHit.rail === 'output' &&
          portHit.portType === 'input'
        ) {
          connectStepOutputToAgentOutput(link.from, link.fromPortIndex, portHit.index);
        } else {
          if (link.fromKind === 'step') {
            const hit = getStepAt(event.offsetX, event.offsetY);
            if (hit) {
              const fromStep = state.steps[link.from];
              if (fromStep) {
                ensureTransition(fromStep, hit.id);
                if (state.selectedStepId === fromStep.id) {
                  renderInspector(fromStep);
                }
                updatePreview();
              }
            }
          }
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
  }
}

async function init() {
  setBanner('');
  registerEventHandlers();

  try {
    await fetchTools();
  } catch (err) {
    console.error('Не вдалося завантажити інструменти', err);
    setBanner('Не вдалося завантажити інструменти. Переконайтеся, що бекенд запущено.');
  }

  try {
    await fetchAgents(true);
  } catch (err) {
    console.error('Не вдалося отримати список агентів', err);
    setBanner('Не вдалося отримати список агентів. Переконайтеся, що бекенд запущено.', 'info');
    if (!Object.keys(state.steps).length) {
      newAgent(true);
    }
  }

  try {
    await fetchAgentsForRunPanel();
  } catch (err) {
    console.error('Не вдалося оновити список агентів для запуску', err);
  }

  ensureRunAgentRow();

  renderAll();
}

init();
