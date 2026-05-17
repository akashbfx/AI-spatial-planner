/**
 * AI Chat Interface — handles user interaction with the chat assistant.
 */

const Chat = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('btn-chat-send');

        sendBtn.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        // Suggestion chips
        document.getElementById('chat-suggestions').addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-chip')) {
                const msg = e.target.dataset.msg;
                input.value = msg;
                this.sendMessage();
            }
        });
    },

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage(message, 'user');
        input.value = '';

        try {
            const response = await Utils.postJSON('/api/chat', { message });

            // Add bot response
            this.addMessage(response.response, 'bot');

            // Update suggestion chips
            this.updateSuggestions(response.suggestions || []);

            // Process actions
            this.processActions(response.actions || [], response);

        } catch (err) {
            this.addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    },

    addMessage(content, type) {
        const container = document.getElementById('chat-messages');

        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-msg ${type}`;

        const avatar = document.createElement('div');
        avatar.className = 'msg-avatar';
        avatar.textContent = type === 'bot' ? '🤖' : '👤';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';

        // Parse markdown-like formatting
        let html = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/• /g, '• ');

        contentDiv.innerHTML = html;

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(contentDiv);
        container.appendChild(msgDiv);

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    },

    updateSuggestions(suggestions) {
        const container = document.getElementById('chat-suggestions');
        container.innerHTML = '';

        for (const text of suggestions) {
            const chip = document.createElement('button');
            chip.className = 'suggestion-chip';
            chip.dataset.msg = text;
            chip.textContent = text;
            container.appendChild(chip);
        }
    },

    processActions(actions, response) {
        for (const action of actions) {
            switch (action.type) {
                case 'add_furniture':
                    ConfigPanel.addFurnitureFromChat(action.category, action.count);
                    Utils.toast(`Added ${action.count}× ${action.category.replace('_', ' ')}`, 'success');
                    break;

                case 'suggest_capacity':
                    // If there's a furniture suggestion, show it
                    if (response.furniture_suggestion) {
                        // Store for later apply
                        this._pendingSuggestion = response.furniture_suggestion;
                    }
                    break;

                case 'confirm_last_action':
                    if (this._pendingSuggestion) {
                        ConfigPanel.furnitureList = [];
                        for (const [cat, count] of Object.entries(this._pendingSuggestion)) {
                            ConfigPanel.addFurnitureFromChat(cat, count);
                        }
                        this._pendingSuggestion = null;
                    }
                    break;

                case 'apply_use_case':
                    document.getElementById('use-case-select').value = action.use_case;
                    break;

                case 'set_preference':
                    if (action.key === 'daylight_priority') {
                        const radio = document.querySelector(`input[name="daylight"][value="${action.value}"]`);
                        if (radio) radio.checked = true;
                    }
                    break;

                case 'set_room_size':
                    document.getElementById('room-width').value = action.width_m;
                    document.getElementById('room-height').value = action.height_m;
                    break;

                case 'remove_furniture':
                    ConfigPanel.furnitureList = ConfigPanel.furnitureList.filter(
                        f => f.category !== action.category
                    );
                    ConfigPanel.updateFurnitureList();
                    break;
            }
        }
    },

    _pendingSuggestion: null,
};
