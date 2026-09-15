const API_BASE = 'http://127.0.0.1:8080';

export async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        return await res.json();
    } catch (e) {
        throw new Error('Backend unreachable');
    }
}

export async function sendChatMessage(message) {
    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            return { error: true, status: res.status, detail: data.detail };
        }
        
        return { error: false, data: data };
    } catch (e) {
        throw new Error('Network error');
    }
}
