import {
    ApiError,
    apiLocation,
    checkHealth,
    createConnection,
    deleteConnection,
    getConnectionCatalog,
    getPolicies,
    importEnvironmentConnections,
    listConnections,
    listTraces,
    sendChatMessage,
    testConnection,
    updatePolicies,
} from './api.js';

const SESSION_TOKEN_KEY = 'guard_ai_operator_token';
const state = {
    token: sessionStorage.getItem(SESSION_TOKEN_KEY) || '',
    catalog: [],
    connections: [],
    traces: [],
    policies: null,
    connectionFilter: 'all',
    connectorFilter: 'all',
    selectedConnector: null,
};

const connectorCopy = {
    guard_demo: 'Live synthetic API backed by SQLite',
    openrouter: 'Hosted multi-model gateway', openai: 'OpenAI models and APIs',
    anthropic: 'Claude model provider', gemini: 'Google Gemini models',
    ollama: 'Local model runtime', custom_ai: 'OpenAI-compatible provider',
    supabase: 'Postgres, Auth, and REST', postgresql: 'PostgreSQL database',
    mysql: 'MySQL database', mongodb: 'MongoDB document store', sqlite: 'Local read-only demo',
    pinecone: 'Managed vector search', qdrant: 'Vector similarity engine',
    s3: 'Object storage bucket', mcp: 'Model Context Protocol server', custom_api: 'External REST service',
};

const categoryLabels = {
    ai_provider: 'AI provider', database: 'Database', vector_store: 'Vector store',
    object_store: 'Object store', mcp_server: 'MCP server', api: 'API',
};

const credentialLabels = {
    api_key: 'API key', username: 'Username', password: 'Password',
    access_key_id: 'Access key ID', secret_access_key: 'Secret access key',
};

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `#icon-${name}`);
    svg.append(use);
    return svg;
}

function initials(label) {
    return label.split(/\s+/).map((word) => word[0]).join('').slice(0, 2).toUpperCase();
}

function formatDate(value, includeDate = false) {
    if (!value) return 'Never';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Unknown';
    return new Intl.DateTimeFormat(undefined, includeDate
        ? { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }
        : { hour: 'numeric', minute: '2-digit', second: '2-digit' }
    ).format(date);
}

function showToast(title, message, type = 'success') {
    const toast = make('div', `toast ${type === 'error' ? 'error' : ''}`);
    const mark = make('div', 'toast-icon', type === 'error' ? '!' : '✓');
    const copy = make('div');
    copy.append(make('strong', '', title), make('span', '', message));
    toast.append(mark, copy);
    $('#toast-region').append(toast);
    window.setTimeout(() => toast.remove(), 4800);
}

function describeError(error) {
    if (error instanceof ApiError) return error.message;
    if (error instanceof TypeError) return 'The backend could not be reached.';
    return 'An unexpected error occurred.';
}

function handleAuthError(error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 503)) {
        lockConsole(false);
        showToast('Operator access required', error.message, 'error');
        openOperatorModal();
        return true;
    }
    return false;
}

function navigate(viewName) {
    const target = $(`#view-${viewName}`);
    if (!target) return;
    $$('.view').forEach((view) => view.classList.toggle('active', view === target));
    $$('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === viewName));
    $('#page-title').textContent = target.dataset.title || viewName;
    $('#sidebar').classList.remove('open');
    $('#mobile-backdrop').classList.remove('open');
    if (viewName === 'activity' && state.token) refreshTraces();
}

function requireOperator(action) {
    if (!state.token) {
        openOperatorModal();
        return false;
    }
    action?.();
    return true;
}

function openOperatorModal() {
    $('#operator-token').value = '';
    $('#operator-modal').showModal();
    window.setTimeout(() => $('#operator-token').focus(), 50);
}

function updateOperatorUi() {
    const button = $('#operator-button');
    const unlocked = Boolean(state.token);
    button.classList.toggle('unlocked', unlocked);
    $('#operator-label').textContent = unlocked ? 'Operator unlocked' : 'Unlock console';
}

function lockConsole(notify = true) {
    state.token = '';
    state.connections = [];
    state.traces = [];
    state.policies = null;
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
    updateOperatorUi();
    renderAll();
    if (notify) showToast('Console locked', 'The operator token was cleared from this tab.');
}

async function unlockConsole(token) {
    const prior = state.token;
    state.token = token;
    try {
        const [connections, policies, traces] = await Promise.all([
            listConnections(token), getPolicies(token), listTraces(token),
        ]);
        state.connections = connections;
        state.policies = policies;
        state.traces = traces;
        sessionStorage.setItem(SESSION_TOKEN_KEY, token);
        updateOperatorUi();
        renderAll();
        $('#operator-modal').close();
        showToast('Console unlocked', 'Private connection, policy, and trace data is now available.');
    } catch (error) {
        state.token = prior;
        throw error;
    }
}

async function loadPrivateData({ quiet = false } = {}) {
    if (!state.token) return;
    try {
        const [connections, policies, traces] = await Promise.all([
            listConnections(state.token), getPolicies(state.token), listTraces(state.token),
        ]);
        state.connections = connections;
        state.policies = policies;
        state.traces = traces;
        renderAll();
    } catch (error) {
        if (!handleAuthError(error) && !quiet) showToast('Could not load console', describeError(error), 'error');
    }
}

async function refreshConnections() {
    if (!state.token) return;
    state.connections = await listConnections(state.token);
    renderConnections();
    renderOverview();
    renderRouteSelectors();
}

async function refreshTraces() {
    if (!state.token) return;
    try {
        state.traces = await listTraces(state.token);
        renderTraces();
        renderOverview();
    } catch (error) {
        if (!handleAuthError(error)) showToast('Could not load activity', describeError(error), 'error');
    }
}

function renderOverview() {
    const verified = state.connections.filter((item) => item.status === 'verified');
    const ai = state.connections.filter((item) => item.category === 'ai_provider');
    const data = state.connections.filter((item) => item.category !== 'ai_provider');
    $('#metric-verified').textContent = verified.length;
    $('#metric-requests').textContent = state.traces.length;
    $('#metric-policy').textContent = state.policies ? `r${state.policies.runtime.revision}` : '—';
    $('#metric-connections-note').textContent = state.token
        ? `${state.connections.length} configured · ${verified.length} verified`
        : 'Unlock to load integrations';
    $('#metric-policy-note').textContent = state.policies
        ? `Updated ${formatDate(state.policies.runtime.updated_at)}`
        : 'Runtime policy state';
    $('#nav-connection-count').textContent = state.connections.length;

    $('#map-ai-label').textContent = ai.length ? `${ai.length} AI ${ai.length === 1 ? 'provider' : 'providers'}` : 'AI providers';
    $('#map-data-label').textContent = data.length ? `${data.length} data & tool ${data.length === 1 ? 'route' : 'routes'}` : 'Databases & tools';
    const aiVerified = ai.some((item) => item.status === 'verified');
    const dataVerified = data.some((item) => item.status === 'verified');
    $('#map-ai-state').textContent = aiVerified ? 'Verified' : ai.length ? 'Configured' : 'Not connected';
    $('#map-data-state').textContent = dataVerified ? 'Verified' : data.length ? 'Configured' : 'Not connected';
    $('#map-ai-state').classList.toggle('online', aiVerified);
    $('#map-data-state').classList.toggle('online', dataVerified);
}

function connectorDefinition(id) {
    return state.catalog.find((item) => item.id === id);
}

function renderConnections() {
    const grid = $('#connection-grid');
    const empty = $('#connections-empty');
    grid.replaceChildren();
    $('#filter-all-count').textContent = state.connections.length;

    const filtered = state.connections.filter((connection) => {
        if (state.connectionFilter === 'all') return true;
        if (state.connectionFilter === 'other') return !['ai_provider', 'database'].includes(connection.category);
        return connection.category === state.connectionFilter;
    });

    empty.classList.toggle('visible', filtered.length === 0);
    grid.hidden = filtered.length === 0;
    for (const connection of filtered) grid.append(buildConnectionCard(connection));
}

function buildConnectionCard(connection) {
    const definition = connectorDefinition(connection.connector);
    const card = make('article', 'connection-card');
    const head = make('div', 'connection-head');
    const logo = make('div', `connector-logo ${connection.category}`, initials(definition?.label || connection.connector));
    const title = make('div', 'connection-title');
    title.append(make('strong', '', connection.name), make('span', '', definition?.label || connection.connector));
    const status = make('span', `status-chip ${connection.status}`, connection.status);
    head.append(logo, title, status);

    const endpoint = make('div', 'connection-endpoint', connection.endpoint);
    endpoint.title = connection.endpoint;
    const meta = make('div', 'connection-meta');
    meta.append(make('span', '', categoryLabels[connection.category] || connection.category));
    meta.append(make('span', '', `${connection.credential_fields.length} secret field${connection.credential_fields.length === 1 ? '' : 's'}`));
    if (connection.last_tested_at) meta.append(make('span', '', `Tested ${formatDate(connection.last_tested_at)}`));

    const actions = make('div', 'connection-actions');
    const testButton = make('button', '', connection.status === 'verified' ? 'Verify again' : 'Test connection');
    testButton.prepend(icon('refresh'));
    testButton.addEventListener('click', () => runConnectionTest(connection, testButton));
    const removeButton = make('button', 'danger-icon');
    removeButton.title = 'Remove connection';
    removeButton.append(icon('trash'));
    removeButton.addEventListener('click', () => removeConnection(connection));
    actions.append(testButton, removeButton);
    card.append(head, endpoint, meta, actions);
    return card;
}

async function runConnectionTest(connection, button) {
    if (!requireOperator()) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Verifying…';
    try {
        const outcome = await testConnection(state.token, connection.id);
        await refreshConnections();
        showToast(outcome.status === 'verified' ? 'Connection verified' : 'Connection checked', outcome.message, outcome.status === 'failed' ? 'error' : 'success');
    } catch (error) {
        if (!handleAuthError(error)) showToast('Verification failed', describeError(error), 'error');
    } finally {
        button.disabled = false;
        button.textContent = original;
    }
}

function confirmRemoval(connection) {
    const dialog = $('#confirm-modal');
    $('#confirm-copy').textContent = `${connection.name} and its stored credentials will be cleared from Guard-AI memory.`;
    dialog.showModal();
    return new Promise((resolve) => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true }));
}

async function removeConnection(connection) {
    if (!await confirmRemoval(connection)) return;
    try {
        await deleteConnection(state.token, connection.id);
        await refreshConnections();
        showToast('Connection removed', `${connection.name} and its in-memory credentials were cleared.`);
    } catch (error) {
        if (!handleAuthError(error)) showToast('Could not remove connection', describeError(error), 'error');
    }
}

async function importConfiguredServices() {
    if (!requireOperator()) return;
    const button = $('#import-env-button');
    button.disabled = true;
    try {
        const result = await importEnvironmentConnections(state.token);
        const candidates = [...result.imported, ...result.existing]
            .filter((connection) => connectorDefinition(connection.connector)?.network_test_supported || connection.connector === 'sqlite');
        await Promise.allSettled(candidates.map((connection) => testConnection(state.token, connection.id)));
        await refreshConnections();
        const imported = result.imported.length;
        const existing = result.existing.length;
        showToast('Server configuration imported', `${imported} added · ${existing} already present · credentials stayed server-side.`);
    } catch (error) {
        if (!handleAuthError(error)) showToast('Import failed', describeError(error), 'error');
    } finally {
        button.disabled = false;
    }
}

function openConnectionModal() {
    if (!requireOperator()) return;
    state.selectedConnector = null;
    state.connectorFilter = 'all';
    showConnectorStep();
    renderConnectorPicker();
    $('#connection-modal').showModal();
}

function showConnectorStep() {
    $('#connector-step').hidden = false;
    $('#connection-form').hidden = true;
    $$('.modal-progress span', $('#connection-modal')).forEach((step, index) => step.classList.toggle('active', index === 0));
}

function renderConnectorPicker() {
    const tabs = $('#connector-tabs');
    const picker = $('#connector-picker');
    tabs.replaceChildren();
    picker.replaceChildren();
    const groups = [
        ['all', 'All services'], ['ai_provider', 'AI providers'], ['database', 'Databases'],
        ['tools', 'Tools & APIs'],
    ];
    for (const [id, label] of groups) {
        const tab = make('button', id === state.connectorFilter ? 'active' : '', label);
        tab.type = 'button';
        tab.addEventListener('click', () => { state.connectorFilter = id; renderConnectorPicker(); });
        tabs.append(tab);
    }

    const filtered = state.catalog.filter((definition) => {
        if (state.connectorFilter === 'all') return true;
        if (state.connectorFilter === 'tools') return !['ai_provider', 'database'].includes(definition.category);
        return definition.category === state.connectorFilter;
    });
    for (const definition of filtered) {
        const option = make('button', 'connector-option');
        option.type = 'button';
        option.append(make('span', `connector-logo ${definition.category}`, initials(definition.label)));
        option.append(make('strong', '', definition.label));
        option.append(make('small', '', connectorCopy[definition.id] || categoryLabels[definition.category]));
        option.addEventListener('click', () => selectConnector(definition));
        picker.append(option);
    }
}

function selectConnector(definition) {
    state.selectedConnector = definition;
    $('#connector-step').hidden = true;
    $('#connection-form').hidden = false;
    $$('.modal-progress span', $('#connection-modal')).forEach((step) => step.classList.add('active'));
    const selected = $('#selected-connector');
    selected.replaceChildren();
    selected.append(make('span', `connector-logo ${definition.category}`, initials(definition.label)));
    const copy = make('div');
    copy.append(make('strong', '', definition.label), make('span', '', connectorCopy[definition.id] || categoryLabels[definition.category]));
    selected.append(copy);

    $('#connection-name').value = `${definition.label} connection`;
    const demoEndpoint = definition.id === 'guard_demo' ? `${apiLocation}/api/v1/demo` : '';
    $('#connection-endpoint').value = definition.default_endpoint || demoEndpoint || (definition.id === 'sqlite' ? 'sqlite:///guard-ai-demo.db' : '');
    $('#connection-endpoint').placeholder = definition.id === 'sqlite' ? 'sqlite:///database.db' : 'https://service.example.com';
    renderConnectorFields(definition);
}

function renderConnectorFields(definition) {
    const settings = $('#connector-settings');
    const credentials = $('#connector-credentials');
    settings.replaceChildren();
    credentials.replaceChildren();

    if (['openrouter', 'openai', 'anthropic', 'gemini', 'custom_ai', 'ollama'].includes(definition.id)) {
        settings.append(buildDynamicField('Model ID (optional)', 'model', false, 'e.g. openai/gpt-4.1'));
    }
    if (definition.id === 'supabase') {
        settings.append(buildDynamicField('Default table or view (optional)', 'table', false, 'e.g. guarded_documents'));
    }
    if (['postgresql', 'mysql', 'mongodb'].includes(definition.id)) {
        settings.append(buildDynamicField('TLS / SSL mode', 'ssl_mode', false, 'verify-full'));
    }
    for (const field of definition.required_credentials) {
        credentials.append(buildDynamicField(credentialLabels[field] || field, field, true, 'Enter secret value'));
    }
}

function buildDynamicField(labelText, key, secret, placeholder) {
    const label = make('label', 'field');
    label.append(make('span', '', labelText));
    const input = document.createElement('input');
    input.type = secret ? 'password' : 'text';
    input.placeholder = placeholder;
    input.required = secret;
    input.autocomplete = secret ? 'new-password' : 'off';
    input.dataset[secret ? 'credential' : 'setting'] = key;
    label.append(input);
    return label;
}

async function saveConnection(event) {
    event.preventDefault();
    const definition = state.selectedConnector;
    if (!definition) return;
    const settings = {};
    const credentials = {};
    $$('[data-setting]', event.currentTarget).forEach((input) => { if (input.value.trim()) settings[input.dataset.setting] = input.value.trim(); });
    $$('[data-credential]', event.currentTarget).forEach((input) => { if (input.value) credentials[input.dataset.credential] = input.value; });
    const payload = {
        name: $('#connection-name').value.trim(),
        category: definition.category,
        connector: definition.id,
        endpoint: $('#connection-endpoint').value.trim(),
        settings,
        credentials,
    };
    const button = $('#save-connection');
    button.disabled = true;
    try {
        const created = await createConnection(state.token, payload);
        $('#connection-modal').close();
        await refreshConnections();
        showToast('Connection saved', `${created.name} was registered without returning its credentials.`);
        if (definition.network_test_supported || definition.id === 'sqlite') {
            const outcome = await testConnection(state.token, created.id);
            await refreshConnections();
            showToast(outcome.status === 'verified' ? 'Trust path verified' : 'Configuration checked', outcome.message, outcome.status === 'failed' ? 'error' : 'success');
        }
    } catch (error) {
        if (!handleAuthError(error)) showToast('Could not save connection', describeError(error), 'error');
    } finally {
        button.disabled = false;
    }
}

function renderRouteSelectors() {
    const aiSelect = $('#ai-route-select');
    const dataSelect = $('#data-route-select');
    const selectedAi = aiSelect.value;
    const selectedData = dataSelect.value;
    aiSelect.replaceChildren(new Option('Guardrail-only simulation', ''));
    dataSelect.replaceChildren(new Option('No data connection', ''));
    for (const connection of state.connections) {
        const suffix = connection.status === 'verified' ? ' · verified' : ' · configured';
        if (connection.category === 'ai_provider') aiSelect.add(new Option(connection.name + suffix, connection.id));
        else dataSelect.add(new Option(connection.name + suffix, connection.id));
    }
    if ([...aiSelect.options].some((option) => option.value === selectedAi)) aiSelect.value = selectedAi;
    if ([...dataSelect.options].some((option) => option.value === selectedData)) dataSelect.value = selectedData;
}

function appendMessage(text, role) {
    const row = make('div', `message ${role}`);
    const avatar = make('div', 'message-avatar');
    avatar.append(role === 'user' ? make('span', '', 'YOU') : icon('shield'));
    const body = make('div');
    body.append(make('span', '', role === 'user' ? 'You' : 'Guard-AI'), make('p', '', text));
    row.append(avatar, body);
    $('#chat-history').append(row);
    $('#chat-history').scrollTop = $('#chat-history').scrollHeight;
}

function renderDecision(response) {
    const status = response.status || 'allowed';
    const statusLabel = status.replace('_', ' ');
    const badge = $('#trace-status');
    badge.className = `trace-status ${status}`;
    badge.textContent = statusLabel;
    const summary = $('#decision-summary');
    summary.className = `decision-summary ${status}`;
    $('strong', summary).textContent = status === 'blocked' ? 'Request blocked safely' : status === 'needs_approval' ? 'Approval required' : 'Request allowed';
    $('p', summary).textContent = `${response.guardrails.length} guardrail stage${response.guardrails.length === 1 ? '' : 's'} completed before the boundary response.`;
    const timeline = $('#decision-timeline');
    timeline.replaceChildren();
    for (const result of response.guardrails) {
        const event = make('div', `decision-event ${result.action}`);
        const heading = make('div');
        heading.append(make('strong', '', result.guardrail), make('b', '', `${result.category} · ${result.action}`));
        event.append(heading, make('p', '', result.reason));
        timeline.append(event);
    }
    $('#trace-reference').hidden = false;
    $('#trace-id').textContent = response.trace_id;
    $('#trace-id').title = response.trace_id;
}

async function submitChat(event) {
    event.preventDefault();
    const input = $('#chat-input');
    const message = input.value.trim();
    if (!message) return;
    const button = $('.send-button');
    appendMessage(message, 'user');
    input.value = '';
    input.style.height = '';
    $('#char-count').textContent = '0 / 100k';
    button.disabled = true;
    try {
        const response = await sendChatMessage(message, {
            aiConnectionId: $('#ai-route-select').value || undefined,
            dataConnectionIds: $('#data-route-select').value ? [$('#data-route-select').value] : [],
        });
        appendMessage(response.response, 'system');
        renderDecision(response);
        if (state.token) await refreshTraces();
    } catch (error) {
        appendMessage('The request could not reach the Guard-AI backend.', 'system');
        showToast('Request failed', describeError(error), 'error');
    } finally {
        button.disabled = false;
        input.focus();
    }
}

function resetChat() {
    const history = $('#chat-history');
    history.replaceChildren();
    appendMessage('I’m ready. Try a normal request, a prompt injection, sensitive output, or a risky action.', 'system');
    $('#trace-status').className = 'trace-status neutral';
    $('#trace-status').textContent = 'Waiting';
    const summary = $('#decision-summary');
    summary.className = 'decision-summary';
    $('strong', summary).textContent = 'No request inspected';
    $('p', summary).textContent = 'Guardrail results will appear here without retaining raw prompt content.';
    $('#decision-timeline').replaceChildren();
    $('#trace-reference').hidden = true;
}

function renderTraces() {
    const table = $('#trace-table');
    const empty = $('#traces-empty');
    table.replaceChildren();
    empty.classList.toggle('visible', state.traces.length === 0);
    table.hidden = state.traces.length === 0;
    $('#activity-total').textContent = state.traces.length;
    $('#activity-allowed').textContent = state.traces.filter((trace) => trace.status === 'allowed').length;
    $('#activity-blocked').textContent = state.traces.filter((trace) => trace.status === 'blocked').length;
    $('#activity-approval').textContent = state.traces.filter((trace) => trace.status === 'needs_approval').length;
    const connectionNames = new Map(state.connections.map((connection) => [connection.id, connection.name]));
    for (const trace of state.traces) {
        const row = make('div', 'trace-row');
        row.append(make('span', '', formatDate(trace.started_at, true)));
        row.append(make('span', `decision-chip ${trace.status}`, trace.status.replace('_', ' ')));
        const routeNames = [];
        if (trace.ai_connection_id) routeNames.push(connectionNames.get(trace.ai_connection_id) || 'AI connection');
        for (const id of trace.data_connection_ids) routeNames.push(connectionNames.get(id) || 'Data connection');
        row.append(make('span', '', routeNames.length ? routeNames.join(' → ') : 'Guardrail simulation'));
        const events = make('span', 'event-dots');
        trace.events.slice(0, 5).forEach((event) => events.append(make('i', event.status)));
        events.append(make('small', '', `${trace.events.length} stages`));
        row.append(events);
        const traceId = make('code', '', trace.trace_id);
        traceId.title = trace.trace_id;
        row.append(traceId);
        table.append(row);
    }
}

function renderPolicies() {
    const disabled = !state.policies;
    $$('[data-policy]').forEach((input) => {
        input.disabled = disabled;
        input.checked = state.policies ? Boolean(state.policies.runtime.policy[input.dataset.policy]) : false;
    });
    $('#policy-revision').textContent = state.policies ? `r${state.policies.runtime.revision}` : '—';
    if (state.policies) {
        $('#transport-group').textContent = state.policies.transport.key_exchange_group;
        $('#transport-tls').textContent = state.policies.transport.tls_version;
    }
}

async function changePolicy(input) {
    if (!requireOperator()) {
        input.checked = !input.checked;
        return;
    }
    input.disabled = true;
    const desired = input.checked;
    try {
        state.policies = await updatePolicies(state.token, { [input.dataset.policy]: desired });
        renderPolicies();
        renderOverview();
        showToast('Policy updated', `${input.dataset.policy.replaceAll('_', ' ')} is now ${desired ? 'enabled' : 'disabled'}.`);
    } catch (error) {
        input.checked = !desired;
        if (!handleAuthError(error)) showToast('Policy update failed', describeError(error), 'error');
    } finally {
        input.disabled = false;
    }
}

function renderAll() {
    renderOverview();
    renderConnections();
    renderRouteSelectors();
    renderTraces();
    renderPolicies();
    updateOperatorUi();
}

function bindEvents() {
    $$('.nav-item').forEach((item) => item.addEventListener('click', () => navigate(item.dataset.view)));
    $$('[data-action="connect"]').forEach((button) => button.addEventListener('click', openConnectionModal));
    $$('[data-action="playground"]').forEach((button) => button.addEventListener('click', () => navigate('playground')));
    $('#quickstart-button').addEventListener('click', () => { navigate('connections'); if (!state.token) openOperatorModal(); });
    $('#operator-button').addEventListener('click', () => state.token ? lockConsole() : openOperatorModal());
    $('#operator-modal-close').addEventListener('click', () => $('#operator-modal').close());
    $('#operator-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const token = $('#operator-token').value.trim();
        const button = $('button[type="submit"]', event.currentTarget);
        button.disabled = true;
        try { await unlockConsole(token); }
        catch (error) { showToast('Unlock failed', describeError(error), 'error'); }
        finally { button.disabled = false; }
    });
    $('#add-connection-button').addEventListener('click', openConnectionModal);
    $('#import-env-button').addEventListener('click', importConfiguredServices);
    $('#connection-modal-close').addEventListener('click', () => $('#connection-modal').close());
    $('#connector-back').addEventListener('click', showConnectorStep);
    $('#connection-form').addEventListener('submit', saveConnection);
    $('#connection-filters').addEventListener('click', (event) => {
        const button = event.target.closest('[data-filter]');
        if (!button) return;
        state.connectionFilter = button.dataset.filter;
        $$('.filter-chip').forEach((chip) => chip.classList.toggle('active', chip === button));
        renderConnections();
    });
    $('#chat-form').addEventListener('submit', submitChat);
    $('#chat-input').addEventListener('input', (event) => {
        event.target.style.height = 'auto';
        event.target.style.height = `${Math.min(event.target.scrollHeight, 120)}px`;
        $('#char-count').textContent = `${event.target.value.length.toLocaleString()} / 100k`;
    });
    $('#chat-input').addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            $('#chat-form').requestSubmit();
        }
    });
    $('#clear-chat').addEventListener('click', resetChat);
    $('#refresh-activity').addEventListener('click', refreshTraces);
    $$('[data-policy]').forEach((input) => input.addEventListener('change', () => changePolicy(input)));
    $('#mobile-menu').addEventListener('click', () => { $('#sidebar').classList.add('open'); $('#mobile-backdrop').classList.add('open'); });
    $('#mobile-backdrop').addEventListener('click', () => { $('#sidebar').classList.remove('open'); $('#mobile-backdrop').classList.remove('open'); });
}

async function initialize() {
    bindEvents();
    $('#sidebar-health-url').textContent = apiLocation.replace(/^https?:\/\//, '') || 'same-origin backend';
    const [healthResult, catalogResult] = await Promise.allSettled([checkHealth(), getConnectionCatalog()]);
    if (healthResult.status === 'fulfilled') {
        $('#sidebar-health-dot').className = 'health-dot online';
        $('#sidebar-health-label').textContent = 'Backend connected';
    } else {
        $('#sidebar-health-dot').className = 'health-dot offline';
        $('#sidebar-health-label').textContent = 'Backend offline';
        showToast('Backend offline', 'Start the Guard-AI API to enable live controls.', 'error');
    }
    if (catalogResult.status === 'fulfilled') state.catalog = catalogResult.value;
    else showToast('Catalog unavailable', 'Connector definitions could not be loaded.', 'error');
    renderAll();
    if (state.token) await loadPrivateData({ quiet: true });
}

initialize();
