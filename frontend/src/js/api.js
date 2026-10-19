const deployedOnVercel = window.location.hostname.endsWith('.vercel.app');
const configuredBase = ((!deployedOnVercel && import.meta.env.VITE_API_URL) || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://127.0.0.1:8080'
        : ''
)).replace(/\/$/, '');

const SERVICE_BASE = configuredBase.replace(/\/api\/v1$/, '');
const API_BASE = `${SERVICE_BASE}/api/v1`;

export class ApiError extends Error {
    constructor(message, status, detail) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.detail = detail;
    }
}

function authHeaders(token) {
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function readableDetail(detail) {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map((item) => item.msg || 'Invalid request').join(' · ');
    }
    return 'The server could not complete the request.';
}

async function request(path, { token, method = 'GET', body, versioned = true } = {}) {
    const response = await fetch(`${versioned ? API_BASE : SERVICE_BASE}${path}`, {
        method,
        headers: {
            Accept: 'application/json',
            ...authHeaders(token),
            ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (response.status === 204) return null;
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
        ? await response.json()
        : null;

    if (!response.ok) {
        const detail = payload?.detail;
        throw new ApiError(readableDetail(detail), response.status, detail);
    }
    return payload;
}

export const apiLocation = SERVICE_BASE || window.location.origin;

export function checkHealth() {
    return request('/health', { versioned: false });
}

export function getConnectionCatalog() {
    return request('/connections/catalog');
}

export function listConnections(token) {
    return request('/connections', { token });
}

export function createConnection(token, connection) {
    return request('/connections', { token, method: 'POST', body: connection });
}

export function importEnvironmentConnections(token) {
    return request('/connections/import-env', { token, method: 'POST' });
}

export function testConnection(token, connectionId) {
    return request(`/connections/${connectionId}/test`, { token, method: 'POST' });
}

export function deleteConnection(token, connectionId) {
    return request(`/connections/${connectionId}`, { token, method: 'DELETE' });
}

export function getPolicies(token) {
    return request('/policies', { token });
}

export function updatePolicies(token, update) {
    return request('/policies', { token, method: 'PUT', body: update });
}

export function listTraces(token, limit = 100) {
    return request(`/traces?limit=${encodeURIComponent(limit)}`, { token });
}

export function sendChatMessage(message, { aiConnectionId, dataConnectionIds = [] } = {}) {
    return request('/chat', {
        method: 'POST',
        body: {
            message,
            ai_connection_id: aiConnectionId || null,
            data_connection_ids: dataConnectionIds,
        },
    });
}
