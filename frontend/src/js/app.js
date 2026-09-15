import { checkHealth, sendChatMessage } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    // Check Health
    const statusIndicator = document.querySelector('.status-indicator');
    const statusText = document.getElementById('backend-status');
    
    checkHealth()
        .then(() => {
            statusIndicator.className = 'status-indicator online';
            statusText.innerText = 'Backend Connected';
        })
        .catch(() => {
            statusIndicator.className = 'status-indicator offline';
            statusText.innerText = 'Backend Offline';
        });

    // Chat Logic
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const telemetryFeed = document.getElementById('telemetry-feed');

    sendBtn.addEventListener('click', handleSend);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });

    async function handleSend() {
        const text = chatInput.value.trim();
        if (!text) return;

        // Add user message to UI
        addChatMessage(text, 'user');
        chatInput.value = '';
        
        // Remove empty state from telemetry
        const emptyState = telemetryFeed.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        try {
            const response = await sendChatMessage(text);
            
            if (response.error) {
                if (response.status === 400) {
                    addChatMessage('Message blocked by Guard-AI.', 'system');
                    addTelemetryEvent('Input Guardrail', 'BLOCKED', response.detail, 'danger');
                } else {
                    addChatMessage('System Error: ' + response.detail, 'system');
                    addTelemetryEvent('System', 'ERROR', response.detail, 'danger');
                }
            } else {
                // Passed Input, maybe Redacted Output
                addChatMessage(response.data.final_response, 'system');
                
                // Add telemetry for Input (Passed)
                addTelemetryEvent('Input Guardrail', 'PASSED', 'Prompt Injection check passed.', 'success');
                
                // Add telemetry for Output (Passed or Redacted)
                if (response.data.guardrail_status.pii_redacted) {
                    addTelemetryEvent('Output Guardrail', 'REDACTED', 'PII detected and redacted from LLM response.', 'warning');
                } else {
                    addTelemetryEvent('Output Guardrail', 'PASSED', 'No PII detected in output.', 'success');
                }
            }
        } catch (error) {
            addChatMessage('Error connecting to backend.', 'system');
        }
    }

    function addChatMessage(text, sender) {
        const div = document.createElement('div');
        div.className = `message ${sender}`;
        const icon = sender === 'user' ? 'fa-user' : 'fa-robot';
        
        div.innerHTML = `
            <div class="avatar"><i class="fa-solid ${icon}"></i></div>
            <div class="bubble">${escapeHTML(text)}</div>
        `;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function addTelemetryEvent(guardrail, status, detail, type) {
        const div = document.createElement('div');
        let className = 'telemetry-event ';
        if (type === 'success') className += 'passed';
        else if (type === 'warning') className += 'redacted';
        else className += 'blocked';
        
        div.className = className;
        
        const time = new Date().toLocaleTimeString();
        
        div.innerHTML = `
            <div class="telemetry-header">
                <strong>${guardrail}</strong>
                <span class="badge ${type}">${status}</span>
            </div>
            <div class="event-details">[${time}] ${escapeHTML(detail)}</div>
        `;
        
        // Add to top of feed
        telemetryFeed.prepend(div);
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
