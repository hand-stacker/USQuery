(function () {
    'use strict';

    const chatEnabled = JSON.parse(document.getElementById('chat_enabled').textContent);
    const fab = document.getElementById('chat-fab');
    const panel = document.getElementById('chat-panel');
    const closeBtn = document.getElementById('chat-close-btn');
    const messagesEl = document.getElementById('chat-messages');
    const inputEl = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    let chatDisplayMode = null;
    let chatDisplayLimit = null;

    if (!fab || !panel) return;

    const billId = parseInt(fab.dataset.billId, 10);
    const hyperBtn = document.getElementById('hyper-mode-btn');
    const usageEl = document.getElementById('chat-usage');
    let sessionId = null;
    let isLoading = false;
    let welcomeShown = false;
    let historyLoaded = false;
    let hyperMode = false;

    if (hyperBtn) {
        hyperBtn.addEventListener('click', function () {
            hyperMode = !hyperMode;
            hyperBtn.classList.toggle('active', hyperMode);
            hyperBtn.title = hyperMode ? 'Hyper Mode ON — HyDE enabled' : 'Hyper Mode — uses HyDE for enhanced retrieval';
        });
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // --- Chat usage widget (donut for Premium, counter for Plus) ---
    function renderChatUsage(data) {
        if (!usageEl) return;
        if (!data || data.display === 'none') {
            usageEl.innerHTML = '';
            return;
        }
        if (data.display === 'donut') {
            const pct = data.val ?? 0;
            const r = 16, sw = 5, cx = 22, cy = 22;
            const circ = 2 * Math.PI * r;
            const filled = pct * circ;
            const color = pct < 0.7 ? '#4ade80' : pct < 0.9 ? '#fbbf24' : '#f87171';
            const pctLabel = Math.round(pct * 100) + '%';
            usageEl.innerHTML =
                '<svg width="44" height="44" viewBox="0 0 44 44" style="flex-shrink:0">' +
                    '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="' + sw + '"/>' +
                    '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="' + sw + '"' +
                        ' stroke-dasharray="' + filled.toFixed(2) + ' ' + (circ - filled).toFixed(2) + '"' +
                        ' stroke-linecap="round" transform="rotate(-90 ' + cx + ' ' + cy + ')"/>' +
                '</svg>' +
                '<div class="chat-usage-text">' +
                    '<span class="chat-usage-amount">' + pctLabel + ' <span class="chat-usage-dim">used</span></span>' +
                    '<span class="chat-usage-label">AI usage this month</span>' +
                '</div>';
        } else if (data.display === 'count') {
            const remaining = data.val ?? 0;
            const limit = data.limit ?? 10;
            const color = remaining > Math.ceil(limit * 0.3) ? '#4ade80' : remaining > 1 ? '#fbbf24' : '#f87171';
            usageEl.innerHTML =
                '<div class="chat-usage-text">' +
                    '<span class="chat-usage-amount" style="color:' + color + '">' +
                        remaining + '<span class="chat-usage-dim"> / ' + limit + '</span>' +
                    '</span>' +
                    '<span class="chat-usage-label">AI chats remaining today</span>' +
                '</div>';
        }
    }

    async function fetchUsage() {
        if (!usageEl || !chatEnabled) return;
        try {
            const resp = await fetch('/bill/chat/usage/', { credentials: 'same-origin' });
            if (!resp.ok) return;
            const data = await resp.json();
            chatDisplayMode = data.display;
            if (data.display === 'count') chatDisplayLimit = data.limit;
            renderChatUsage(data);
        } catch (_) {}
    }

    // --- History load ---
    async function loadHistory() {
        try {
            const resp = await fetch('/bill/chat/history/?bill_id=' + billId, { credentials: 'same-origin' });
            if (resp.ok) {
                const data = await resp.json();
                if (data.session_id && data.messages && data.messages.length > 0) {
                    sessionId = data.session_id;
                    welcomeShown = true;
                    data.messages.forEach(function (m) {
                        appendMessage(m.role, m.content);
                    });
                    return;
                }
            }
        } catch (_) {}
        if (!welcomeShown) {
            welcomeShown = true;
            appendMessage('assistant', 'Hi! I\'m your AI legislative assistant. Ask me anything about this bill — its provisions, potential impact, or legislative history.');
        }
    }

    // --- Panel open/close ---
    fab.addEventListener('click', function () {
        panel.classList.add('open');
        fab.style.display = 'none';
        if (chatEnabled && !historyLoaded) {
            historyLoaded = true;
            loadHistory();
        }
        fetchUsage();
        if (inputEl) inputEl.focus();
    });

    closeBtn.addEventListener('click', function () {
        panel.classList.remove('open');
        fab.style.display = '';
    });

    // --- Message rendering ---
    function appendMessage(role, content, sources) {
        const msg = document.createElement('div');
        msg.className = 'chat-msg ' + role;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        if (role === 'assistant' && typeof marked !== 'undefined') {
            bubble.innerHTML = marked.parse(content);
        } else {
            bubble.textContent = content;
        }
        msg.appendChild(bubble);

        if (sources && sources.length > 0) {
            const sourcesEl = document.createElement('div');
            sourcesEl.className = 'chat-sources';
            const label = document.createElement('span');
            label.className = 'chat-sources-label';
            label.textContent = 'Sources: ';
            sourcesEl.appendChild(label);
            sources.forEach(function (url, i) {
                if (i > 0) {
                    const sep = document.createElement('span');
                    sep.textContent = ' · ';
                    sep.style.opacity = '0.4';
                    sourcesEl.appendChild(sep);
                }
                const a = document.createElement('a');
                a.href = 'https://www.' + url;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                a.className = 'chat-source-link';
                const lower = url.toLowerCase();
                a.textContent = lower.endsWith('.pdf') ? 'PDF ' + (i + 1)
                              : lower.endsWith('.xlsx') ? 'XLSX ' + (i + 1)
                              : 'Source ' + (i + 1);
                sourcesEl.appendChild(a);
            });
            msg.appendChild(sourcesEl);
        }

        messagesEl.appendChild(msg);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function showTyping() {
        const el = document.createElement('div');
        el.className = 'chat-msg assistant';
        el.id = 'chat-typing';
        el.innerHTML = '<div class="chat-typing-indicator">' +
            '<div class="chat-typing-dot"></div>' +
            '<div class="chat-typing-dot"></div>' +
            '<div class="chat-typing-dot"></div>' +
            '</div>';
        messagesEl.appendChild(el);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('chat-typing');
        if (el) el.remove();
    }

    // --- Send ---
    async function sendMessage() {
        if (!chatEnabled || isLoading) return;
        const text = (inputEl.value || '').trim();
        if (!text) return;

        isLoading = true;
        inputEl.value = '';
        inputEl.disabled = true;
        sendBtn.disabled = true;

        appendMessage('user', text);
        showTyping();

        try {
            const resp = await fetch('/bill/chat/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                },
                body: JSON.stringify({ bill_id: billId, message: text, session_id: sessionId, hyper_mode: hyperMode }),
            });

            removeTyping();

            if (!resp.ok) {
                appendMessage('system', 'Server error (' + resp.status + '). Please try again.');
                return;
            }

            const data = await resp.json();

            if (data.error) {
                if (data.error === 'UPGRADE_REQUIRED') {
                    appendMessage('system', 'Upgrade to Plus or Premium to use the AI assistant.');
                } else if (data.error === 'RATE_LIMITED') {
                    appendMessage('system', 'Daily message limit reached. Try again tomorrow or upgrade your plan.');
                } else if (data.error === 'MONTHLY_LIMIT_REACHED') {
                    appendMessage('system', 'Monthly AI usage limit reached. Your limit resets at the start of next month.');
                } else if (data.error === 'AI_OVERLOADED') {
                    appendMessage('system', 'The AI is temporarily overloaded. Please wait a moment and try again.');
                } else {
                    appendMessage('system', data.error);
                }
            } else {
                appendMessage('assistant', data.assistant_message, data.sources || []);
                sessionId = data.session_id;
                if (chatDisplayMode === 'count') {
                    renderChatUsage({ display: 'count', val: data.messages_remaining, limit: chatDisplayLimit });
                } else {
                    fetchUsage();
                }
            }
        } catch (err) {
            removeTyping();
            appendMessage('system', 'Connection error. Please try again.');
        } finally {
            isLoading = false;
            inputEl.disabled = false;
            sendBtn.disabled = false;
            inputEl.focus();
        }
    }

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);

    if (inputEl) {
        inputEl.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
})();
