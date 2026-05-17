/**
 * SpaceAI — Main Application Orchestration with theme toggle
 */

const App = {
    generatedData: null,
    theme: 'dark',
    _generateLock: false,  // Debounce lock

    async init() {
        console.log('🚀 SpaceAI initializing...');

        // Load saved theme
        this.theme = localStorage.getItem('spaceai-theme') || 'dark';
        this.applyTheme(this.theme);

        // Initialize modules
        RoomCanvas.init();
        await ConfigPanel.init();
        FurnitureCreator.init();
        Chat.init();
        Export.init();

        this.bindEvents();

        console.log('✅ SpaceAI ready!');
    },

    bindEvents() {
        // Generate layouts button
        document.getElementById('btn-generate').addEventListener('click', () => this.generateLayouts());

        // Mode buttons
        document.getElementById('btn-draw-mode').addEventListener('click', () => this.setViewMode('draw'));
        document.getElementById('btn-config-mode').addEventListener('click', () => this.setViewMode('config'));
        document.getElementById('btn-results-mode').addEventListener('click', () => this.setViewMode('results'));

        // Close results
        document.getElementById('btn-close-results').addEventListener('click', () => LayoutViewer.closeResults());

        // Close modal
        document.getElementById('btn-modal-close').addEventListener('click', () => LayoutViewer.closeModal());

        // Modal backdrop click
        document.getElementById('layout-modal').addEventListener('click', (e) => {
            if (e.target.id === 'layout-modal') LayoutViewer.closeModal();
        });

        // Theme toggle
        const themeBtn = document.getElementById('btn-theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', () => this.toggleTheme());
        }

        // Engine mode toggle
        const engineToggle = document.getElementById('engine-mode-toggle');
        if (engineToggle) {
            engineToggle.addEventListener('change', (e) => {
                const mode = e.target.checked ? 'quality' : 'hybrid';
                localStorage.setItem('spaceai-engine-mode', mode);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                LayoutViewer.closeModal();
            }
            if (e.ctrlKey && e.key === 'g') {
                e.preventDefault();
                this.generateLayouts();
            }
        });

        // Prevent right-click menu on canvas (for wall vertex deletion)
        document.getElementById('canvas-container').addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
    },

    // ─── Theme ───────────────────────────────────────────────────

    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme(this.theme);
        localStorage.setItem('spaceai-theme', this.theme);
    },

    applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-theme');
        } else {
            document.body.classList.remove('light-theme');
        }

        // Update theme toggle button icon
        const themeBtn = document.getElementById('btn-theme-toggle');
        if (themeBtn) {
            themeBtn.innerHTML = theme === 'dark'
                ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
                : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>';
        }

        // Update canvas theme
        if (typeof RoomCanvas !== 'undefined' && RoomCanvas.canvas) {
            RoomCanvas.updateTheme();
        }
    },

    // ─── View Modes ──────────────────────────────────────────────

    setViewMode(mode) {
        document.querySelectorAll('.header-btn').forEach(b => b.classList.remove('active'));

        switch (mode) {
            case 'draw':
                document.getElementById('btn-draw-mode').classList.add('active');
                document.getElementById('canvas-panel').style.display = '';
                document.getElementById('sidebar').style.display = '';
                document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelector('[data-tab="room-tab"]').classList.add('active');
                document.getElementById('room-tab').classList.add('active');
                break;

            case 'config':
                document.getElementById('btn-config-mode').classList.add('active');
                document.getElementById('canvas-panel').style.display = '';
                document.getElementById('sidebar').style.display = '';
                document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelector('[data-tab="furniture-tab"]').classList.add('active');
                document.getElementById('furniture-tab').classList.add('active');
                break;

            case 'results':
                document.getElementById('btn-results-mode').classList.add('active');
                if (this.generatedData) {
                    LayoutViewer.showResults(this.generatedData);
                } else {
                    Utils.toast('Generate layouts first!', 'warning');
                }
                break;
        }
    },

    // ─── Generation ──────────────────────────────────────────────

    async generateLayouts() {
        // Debounce: prevent double-clicks
        if (this._generateLock) {
            Utils.toast('Generation already in progress...', 'info');
            return;
        }

        if (!RoomCanvas.roomClosed || RoomCanvas.walls.length < 3) {
            Utils.toast('Draw a room first! Click to place wall corners, then close the shape.', 'warning');
            return;
        }

        if (ConfigPanel.furnitureList.length === 0) {
            Utils.toast('Add furniture first! Use the catalog, Smart Suggest, or AI Chat.', 'warning');
            return;
        }

        this._generateLock = true;
        const loading = document.getElementById('loading-overlay');
        loading.classList.remove('hidden');

        const startMs = performance.now();

        try {
            const roomData = RoomCanvas.getRoomData();
            const furniture = ConfigPanel.getFurnitureForAPI();
            const preferences = ConfigPanel.getPreferences();

            // Read engine mode preference
            const engineToggle = document.getElementById('engine-mode-toggle');
            if (engineToggle && engineToggle.checked) {
                preferences.engine_mode = 'quality';
            } else {
                preferences.engine_mode = 'hybrid';
            }

            const data = await Utils.postJSON('/api/generate-layouts', {
                room: roomData,
                furniture: furniture,
                preferences: preferences,
            });

            if (data.error) {
                throw new Error(data.error);
            }

            const clientMs = Math.round(performance.now() - startMs);

            // Inject timing metadata for display
            data._client_ms = clientMs;

            this.generatedData = data;
            loading.classList.add('hidden');
            LayoutViewer.showResults(data);

            document.querySelectorAll('.header-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('btn-results-mode').classList.add('active');

            // Show performance toast
            const engine = data.engine || 'hybrid';
            const serverMs = data._request_ms || data.time_seconds * 1000;
            const cached = data._cache_hit ? ' (cached)' : '';
            Utils.toast(
                `Generated in ${Math.round(serverMs)}ms${cached} · ${engine} engine`,
                'success'
            );

        } catch (err) {
            loading.classList.add('hidden');
            Utils.toast('Layout generation failed: ' + err.message, 'error');
            console.error('Generation error:', err);
        } finally {
            this._generateLock = false;
        }
    },
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => App.init());
