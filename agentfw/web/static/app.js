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
};

const canvas = document.getElementById('graphCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;

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
  return {
    id,
    name: raw.name || defaultNameFromKind(kind),
    kind,
    toolName: raw.toolName || raw.tool_name || raw.tool || null,
    toolParams: raw.toolParams || raw.tool_params || {},
    inputs: Array.isArray(raw.inputs) ? raw.inputs : [],
    saveMapping: normalizeSaveMapping(raw.saveMapping || raw.save_mapping),
    validatorAgentName: raw.validator_agent_name || raw.validatorAgentName || '',
    validatorParams: raw.validator_params || raw.validatorParams || {},
    validatorPolicy: raw.validator_policy || raw.validatorPolicy || {},
    transitions: (raw.transitions || []).map((tr) => normalizeTransition(tr, id)),
    x: raw.x ?? 80 + (defaultPosition % 4) * 180,
    y: raw.y ?? 80 + Math.floor(defaultPosition / 4) * 140,
  };
}

function createStep(kind) {
  const id = generateStepId(kind);
  const base = normalizeStep({ id, kind, name: defaultNameFromKind(kind) });
  if (kind === 'loop') {
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

function populateToolAndConditionOptions() {
  const toolSelect = document.getElementById('toolName');
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

  const condSelect = document.getElementById('conditionType');
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
  state.agents.forEach((name) => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
}

function addStep(step) {
  if (!step.id) return;
  state.steps[step.id] = normalizeStep(step);
  refreshSelectors();
  render();
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
  return Object.values(state.steps).find(
    (step) => x >= step.x && x <= step.x + 140 && y >= step.y && y <= step.y + 60,
  );
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
      });

      const from = document.createElement('input');
      from.placeholder = 'Брати зі змінної агента';
      from.value = inp.fromVar || '';
      from.addEventListener('input', () => {
        step.inputs[idx].fromVar = from.value;
        updatePreview();
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
    step.inputs.push({ name: '', fromVar: '', defaultValue: '', description: '' });
    renderInputs();
    updatePreview();
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
    if (!props) {
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
      return;
    }

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
      });

      const varInput = document.createElement('input');
      varInput.placeholder = 'Записати в змінну агента';
      varInput.value = m.varName || '';
      varInput.addEventListener('input', () => {
        step.saveMapping[idx].varName = varInput.value;
        updatePreview();
      });

      const descInput = document.createElement('input');
      descInput.placeholder = 'Опис';
      descInput.value = m.description || '';
      descInput.addEventListener('input', () => {
        step.saveMapping[idx].description = descInput.value;
        updatePreview();
      });

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '✕';
      remove.addEventListener('click', () => {
        step.saveMapping.splice(idx, 1);
        renderOutputs();
        updatePreview();
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
      inputs: step.inputs || [],
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

  Object.values(state.steps).forEach((step) => {
    (step.transitions || []).forEach((tr) => {
      const target = state.steps[tr.targetStepId];
      if (!target) return;
      const startX = step.x + 70;
      const startY = step.y + 30;
      const endX = target.x + 70;
      const endY = target.y + 30;
      ctx.strokeStyle = '#1d5dff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      if (step.id === target.id) {
        ctx.moveTo(startX, startY);
        ctx.quadraticCurveTo(startX + 60, startY - 60, startX, startY - 10);
        ctx.quadraticCurveTo(startX - 60, startY - 60, startX, startY);
      } else {
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
      }
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
        const midX = step.id === target.id ? startX + 10 : (startX + endX) / 2;
        const midY = step.id === target.id ? startY - 50 : (startY + endY) / 2;
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
    ctx.fillText(step.name || step.id, step.x + 10, step.y + 20);
    ctx.font = '12px Inter';
    const meta = state.tools.find((t) => t.name === step.toolName);
    const label = meta ? toolLabel(meta) : step.toolName || '';
    ctx.fillText(label, step.x + 10, step.y + 38);
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
  withElement('runAgentName', (el) => {
    el.value = '';
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
  const tool = evt.dataTransfer.getData('text/plain');
  if (!tool) return;
  const rect = canvas.getBoundingClientRect();
  const x = evt.clientX - rect.left - 70;
  const y = evt.clientY - rect.top - 30;
  const id = generateStepId(tool || 'step');
  addStep({ id, name: defaultNameFromKind('action'), kind: 'action', toolName: tool, x, y });
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
  if (!container) return;
  container.innerHTML = '';
  const status = document.createElement('div');
  status.className = data.failed ? 'status-badge bad' : 'status-badge good';
  status.textContent = data.failed ? 'невдача' : 'успіх';
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

function renderAll() {
  render();
  updatePreview();
  if (state.selectedStepId) {
    renderInspector(state.steps[state.selectedStepId]);
  }
}

async function init() {
  await fetchTools();
  withElement('saveAgent', (el) => el.addEventListener('click', saveAgent));
  withElement('validateAgent', (el) => el.addEventListener('click', validateAgent));
  withElement('loadAgent', (el) => el.addEventListener('click', loadAgent));
  withElement('newAgent', (el) => el.addEventListener('click', newAgent));
  withElement('refreshAgents', (el) => el.addEventListener('click', () => fetchAgents()));
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
  withElement('runAgent', (el) => el.addEventListener('click', runAgent));

  if (canvas) {
    canvas.addEventListener('mousedown', startDrag);
    canvas.addEventListener('mousemove', onDrag);
    canvas.addEventListener('mouseup', (event) => {
      if (state.draggingLink) {
        const hit = getStepAt(event.offsetX, event.offsetY);
        if (hit && hit.id !== state.draggingLink.from) {
          const fromStep = state.steps[state.draggingLink.from];
          fromStep.transitions = fromStep.transitions || [];
          fromStep.transitions.push({
            id: generateTransitionId(),
            targetStepId: hit.id,
            condition: { type: 'always', params: {} },
          });
          refreshSelectors();
          renderInspector(fromStep);
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
  }

  await fetchAgents(true);
  renderAll();
}

init();
