/**
 * Configuration Panel — Room, Furniture, and Preferences management.
 */

const ConfigPanel = {
    catalog: null,
    furnitureList: [],  // { piece_id, name, category, width, depth, count, color }

    async init() {
        // Load catalog
        try {
            this.catalog = await Utils.fetchJSON('/api/furniture-catalog');
            this.populateCatalogSelect();
            this.populateCategorySelect();
        } catch (err) {
            console.error('Failed to load catalog:', err);
        }

        // Load presets
        try {
            const data = await Utils.fetchJSON('/api/room-presets');
            this.populatePresets(data.presets);
        } catch (err) {
            console.error('Failed to load presets:', err);
        }

        this.bindEvents();
    },

    populateCatalogSelect() {
        const select = document.getElementById('catalog-select');
        select.innerHTML = '';

        if (!this.catalog) return;

        const categories = {};
        for (const piece of this.catalog.furniture) {
            if (!categories[piece.category]) categories[piece.category] = [];
            categories[piece.category].push(piece);
        }

        for (const [cat, pieces] of Object.entries(categories)) {
            const group = document.createElement('optgroup');
            group.label = this.catalog.categories[cat] || cat;

            for (const p of pieces) {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `${p.name} (${p.width}×${p.depth}cm)`;
                group.appendChild(opt);
            }
            select.appendChild(group);
        }
    },

    populateCategorySelect() {
        const select = document.getElementById('custom-category');
        select.innerHTML = '';

        const cats = this.catalog?.categories || {};
        for (const [key, label] of Object.entries(cats)) {
            const opt = document.createElement('option');
            opt.value = key;
            opt.textContent = label;
            select.appendChild(opt);
        }
    },

    populatePresets(presets) {
        const container = document.getElementById('preset-buttons');
        container.innerHTML = '';

        for (const preset of presets) {
            const btn = document.createElement('button');
            btn.textContent = preset.name;
            btn.title = preset.description;
            btn.addEventListener('click', () => {
                RoomCanvas.loadPreset(preset);
            });
            container.appendChild(btn);
        }
    },

    bindEvents() {
        // Apply dimensions
        document.getElementById('btn-apply-dimensions').addEventListener('click', () => {
            const w = parseFloat(document.getElementById('room-width').value) || 8;
            const h = parseFloat(document.getElementById('room-height').value) || 6;
            RoomCanvas.loadRectRoom(w, h);
        });

        // Add from catalog
        document.getElementById('btn-add-catalog').addEventListener('click', () => {
            const select = document.getElementById('catalog-select');
            const pieceId = select.value;
            const count = parseInt(document.getElementById('furn-count').value) || 1;

            const piece = this.catalog?.furniture?.find(p => p.id === pieceId);
            if (!piece) return;

            // Check if already in list
            const existing = this.furnitureList.find(f => f.piece_id === pieceId);
            if (existing) {
                existing.count += count;
            } else {
                this.furnitureList.push({
                    piece_id: piece.id,
                    name: piece.name,
                    category: piece.category,
                    width: piece.width,
                    depth: piece.depth,
                    count: count,
                    color: piece.color || '#888',
                });
            }

            this.updateFurnitureList();
            Utils.toast(`Added ${count}× ${piece.name}`, 'success');
        });

        // Add custom
        document.getElementById('btn-add-custom').addEventListener('click', () => {
            const name = document.getElementById('custom-name').value || 'Custom Piece';
            const category = document.getElementById('custom-category').value;
            const width = parseInt(document.getElementById('custom-width').value) || 120;
            const depth = parseInt(document.getElementById('custom-depth').value) || 60;

            this.furnitureList.push({
                piece_id: null,
                name: name,
                category: category,
                width: width,
                depth: depth,
                count: 1,
                color: this.getCategoryColor(category),
                is_custom: true,
            });

            this.updateFurnitureList();
            Utils.toast(`Added custom: ${name}`, 'success');
        });

        // Add door from config
        document.getElementById('btn-add-door-config').addEventListener('click', () => {
            if (!RoomCanvas.roomClosed) {
                Utils.toast('Draw a room first', 'warning');
                return;
            }
            RoomCanvas.setMode('add_door');
            // Switch to canvas
            Utils.toast('Click on a wall in the canvas to place a door', 'info');
        });

        // Add window from config
        document.getElementById('btn-add-window-config').addEventListener('click', () => {
            if (!RoomCanvas.roomClosed) {
                Utils.toast('Draw a room first', 'warning');
                return;
            }
            RoomCanvas.setMode('add_window');
            Utils.toast('Click on a wall in the canvas to place a window', 'info');
        });

        // Smart suggest
        document.getElementById('btn-smart-suggest').addEventListener('click', () => this.smartSuggest());

        // Sun orientation
        const sunSlider = document.getElementById('sun-orientation');
        sunSlider.addEventListener('input', () => {
            const val = parseInt(sunSlider.value);
            document.getElementById('sun-value').textContent = `${val}° (${Utils.compassLabel(val)})`;
            document.getElementById('compass-needle').style.transform = `rotate(${val}deg)`;
        });

        // Compass direction clicks
        document.querySelectorAll('.compass-dir').forEach(dir => {
            dir.addEventListener('click', () => {
                const val = parseInt(dir.dataset.dir);
                sunSlider.value = val;
                sunSlider.dispatchEvent(new Event('input'));
            });
        });

        // Sidebar tabs
        document.querySelectorAll('.sidebar-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
        });
    },

    getCategoryColor(cat) {
        const colors = {
            work_desk: '#4A90D9',
            shared_table: '#50B86C',
            meeting_table: '#E8833A',
            chair: '#9B59B6',
            storage: '#7F8C8D',
            collaborative_seating: '#1ABC9C',
            lounge: '#E74C3C',
        };
        return colors[cat] || '#888';
    },

    updateFurnitureList() {
        const container = document.getElementById('furniture-list');
        container.innerHTML = '';

        if (this.furnitureList.length === 0) {
            container.innerHTML = '<p style="font-size:0.75rem;color:#6868a0;text-align:center;padding:12px;">No furniture added yet. Use catalog or Smart Suggest.</p>';
            return;
        }

        for (let i = 0; i < this.furnitureList.length; i++) {
            const item = this.furnitureList[i];
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = `
                <div class="item-color" style="background:${item.color}"></div>
                <div class="item-info">
                    <div class="item-name">${item.name}</div>
                    <div class="item-meta">${item.width}×${item.depth}cm · ${item.category}</div>
                </div>
                <div class="item-count">
                    <input type="number" value="${item.count}" min="1" max="50" data-idx="${i}">
                </div>
                <button class="item-remove" data-idx="${i}" title="Remove">×</button>
            `;
            container.appendChild(card);
        }

        // Bind count change
        container.querySelectorAll('.item-count input').forEach(input => {
            input.addEventListener('change', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                this.furnitureList[idx].count = parseInt(e.target.value) || 1;
            });
        });

        // Bind remove
        container.querySelectorAll('.item-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                this.furnitureList.splice(idx, 1);
                this.updateFurnitureList();
            });
        });
    },

    updateDoorsList() {
        const container = document.getElementById('doors-list');
        container.innerHTML = '';

        for (let i = 0; i < RoomCanvas.doors.length; i++) {
            const door = RoomCanvas.doors[i];
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = `
                <div class="item-color" style="background:#4FC3F7"></div>
                <div class="item-info">
                    <div class="item-name">Door ${i + 1}</div>
                    <div class="item-meta">Wall ${door.wall_index + 1} · ${door.width}cm</div>
                </div>
                <div class="item-count">
                    <input type="number" value="${door.width}" min="60" max="200" step="10" data-idx="${i}" class="door-width-input" style="width:50px;">
                    <span style="font-size:0.65rem;color:#6868a0;">cm</span>
                </div>
                <button class="item-remove" data-idx="${i}" title="Remove">×</button>
            `;
            container.appendChild(card);
        }

        container.querySelectorAll('.door-width-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                RoomCanvas.doors[idx].width = parseInt(e.target.value) || 90;
                RoomCanvas.redrawRoom();
            });
        });

        container.querySelectorAll('.item-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                RoomCanvas.doors.splice(idx, 1);
                RoomCanvas.redrawRoom();
                this.updateDoorsList();
            });
        });
    },

    updateWindowsList() {
        const container = document.getElementById('windows-list');
        container.innerHTML = '';

        for (let i = 0; i < RoomCanvas.windows.length; i++) {
            const win = RoomCanvas.windows[i];
            const card = document.createElement('div');
            card.className = 'item-card';
            card.innerHTML = `
                <div class="item-color" style="background:#FFD54F"></div>
                <div class="item-info">
                    <div class="item-name">Window ${i + 1}</div>
                    <div class="item-meta">Wall ${win.wall_index + 1} · ${win.width}cm</div>
                </div>
                <div class="item-count">
                    <input type="number" value="${win.width}" min="40" max="400" step="10" data-idx="${i}" class="win-width-input" style="width:50px;">
                    <span style="font-size:0.65rem;color:#6868a0;">cm</span>
                </div>
                <button class="item-remove" data-idx="${i}" title="Remove">×</button>
            `;
            container.appendChild(card);
        }

        container.querySelectorAll('.win-width-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                RoomCanvas.windows[idx].width = parseInt(e.target.value) || 120;
                RoomCanvas.redrawRoom();
            });
        });

        container.querySelectorAll('.item-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.idx);
                RoomCanvas.windows.splice(idx, 1);
                RoomCanvas.redrawRoom();
                this.updateWindowsList();
            });
        });
    },

    async smartSuggest() {
        if (!RoomCanvas.roomClosed) {
            Utils.toast('Draw a room first', 'warning');
            return;
        }

        const useCase = document.getElementById('use-case-select').value;
        const roomData = RoomCanvas.getRoomData();

        try {
            const result = await Utils.postJSON('/api/smart-suggest', {
                room: roomData,
                use_case: useCase,
            });

            const container = document.getElementById('suggest-result');
            container.classList.remove('hidden');

            if (useCase === 'analyze') {
                // Show recommendations
                const analysis = result.room_analysis;
                const recs = result.recommendations;
                let html = `<div style="margin-bottom:8px;"><strong>Room:</strong> ${analysis.area_sqm} sqm, ${analysis.shape} shape, ${analysis.num_windows} windows</div>`;
                html += `<div style="margin-bottom:8px;font-weight:600;">Top Recommendations:</div>`;
                for (const rec of recs.slice(0, 3)) {
                    html += `<div class="suggest-item"><span>${rec.use_case.replace('_', ' ')}</span><strong style="color:${rec.fit_score >= 85 ? '#50B86C' : '#4A90D9'}">${rec.fit_score}%</strong></div>`;
                    html += `<div style="font-size:0.68rem;color:#6868a0;margin-bottom:4px;">${rec.reason}</div>`;
                }
                container.innerHTML = html;
            } else {
                let html = `<div style="margin-bottom:6px;"><strong>${result.label}</strong></div>`;
                html += `<div style="font-size:0.7rem;color:#9898b8;margin-bottom:8px;">${result.description}</div>`;
                html += `<div class="suggest-item"><span>Capacity</span><strong>${result.estimated_capacity} people</strong></div>`;
                html += `<div class="suggest-item"><span>Utilization</span><strong>${result.estimated_utilization}%</strong></div>`;
                html += `<div style="margin-top:8px;font-weight:600;font-size:0.78rem;">Suggested Furniture:</div>`;

                for (const f of result.furniture) {
                    html += `<div class="suggest-item"><span>${f.piece_name}</span><strong>×${f.count}</strong></div>`;
                }

                html += `<button class="btn-secondary suggest-apply" onclick="ConfigPanel.applySuggestion()" style="margin-top:10px;">Apply This Configuration</button>`;
                container.innerHTML = html;
                container._suggestion = result;
            }

        } catch (err) {
            Utils.toast('Smart suggest failed: ' + err.message, 'error');
        }
    },

    applySuggestion() {
        const container = document.getElementById('suggest-result');
        const suggestion = container._suggestion;
        if (!suggestion) return;

        this.furnitureList = [];

        for (const f of suggestion.furniture) {
            this.furnitureList.push({
                piece_id: f.piece_id,
                name: f.piece_name,
                category: f.category,
                width: f.width,
                depth: f.depth,
                count: f.count,
                color: this.getCategoryColor(f.category),
            });
        }

        this.updateFurnitureList();
        Utils.toast('Furniture configuration applied!', 'success');

        // Switch to furniture tab
        document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector('[data-tab="furniture-tab"]').classList.add('active');
        document.getElementById('furniture-tab').classList.add('active');
    },

    getPreferences() {
        return {
            sun_orientation: parseInt(document.getElementById('sun-orientation').value) || 180,
            daylight_priority: document.querySelector('input[name="daylight"]:checked')?.value || 'medium',
            circulation_width: parseInt(document.getElementById('circulation-width').value) || 90,
            use_case: document.getElementById('use-case-select')?.value || 'hybrid_flex',
        };
    },

    getFurnitureForAPI() {
        return this.furnitureList.map(f => ({
            piece_id: f.piece_id,
            category: f.category,
            name: f.name,
            width: f.width,
            depth: f.depth,
            count: f.count,
        }));
    },

    // Add furniture from chat action
    addFurnitureFromChat(category, count) {
        const piece = this.catalog?.furniture?.find(p => p.category === category);
        const existing = this.furnitureList.find(f => f.category === category);

        if (existing) {
            existing.count += count;
        } else {
            this.furnitureList.push({
                piece_id: piece?.id || null,
                name: piece?.name || category.replace('_', ' '),
                category: category,
                width: piece?.width || 120,
                depth: piece?.depth || 60,
                count: count,
                color: this.getCategoryColor(category),
            });
        }
        this.updateFurnitureList();
    },
};
