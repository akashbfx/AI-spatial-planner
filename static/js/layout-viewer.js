/**
 * Layout Viewer — renders generated layouts using architectural furniture symbols.
 */

const LayoutViewer = {
    layouts: [],
    currentLayout: null,
    radarChart: null,

    showResults(data) {
        this.layouts = data.layouts || [];

        const panel = document.getElementById('results-panel');
        panel.classList.remove('hidden');

        // Show engine timing info
        const engine = data.engine || 'hybrid';
        const timeMs = data._request_ms || (data.time_seconds * 1000);
        const cached = data._cache_hit ? ' (cached)' : '';
        const engineLabel = engine === 'hybrid' ? '⚡ Hybrid' : '🧬 GA';

        document.getElementById('results-time').textContent = `⏱ ${Math.round(timeMs)}ms${cached}`;
        document.getElementById('results-generations').textContent =
            data.timing
                ? `${engineLabel} · Grid ${data.timing.grid_engine_ms}ms · ML ${data.timing.ml_refinement_ms}ms`
                : `${engineLabel} · ${data.generations_run || 0} generations`;

        // Adjust main layout
        document.getElementById('app-main').style.height = 'calc(100vh - 56px - 300px)';

        const grid = document.getElementById('layouts-grid');
        grid.innerHTML = '';

        for (let i = 0; i < this.layouts.length; i++) {
            const layout = this.layouts[i];
            const card = this.createLayoutCard(layout, i, data);
            grid.appendChild(card);
        }

        // Enable export buttons
        document.getElementById('btn-export-svg').disabled = false;
        document.getElementById('btn-export-png').disabled = false;

        Utils.toast(`Generated ${this.layouts.length} layouts!`, 'success');
    },

    createLayoutCard(layout, index, data) {
        const card = document.createElement('div');
        card.className = 'layout-card';
        card.addEventListener('click', () => this.openDetail(layout, data));

        // Mini canvas
        const canvasDiv = document.createElement('div');
        canvasDiv.className = 'layout-card-canvas';
        const cvs = document.createElement('canvas');
        cvs.width = 280;
        cvs.height = 150;
        canvasDiv.appendChild(cvs);
        card.appendChild(canvasDiv);

        // Draw mini layout
        this.drawMiniLayout(cvs, layout, data);

        // Info
        const info = document.createElement('div');
        info.className = 'layout-card-info';

        const scores = layout.scores;
        const gradeClass = `grade-${scores.grade.replace('+', '\\+')}`;

        info.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-weight:600;font-size:0.85rem;">Layout ${layout.layout_id}</span>
                <span class="layout-card-grade ${gradeClass}">${scores.grade}</span>
            </div>
            <div class="layout-card-scores">
                <div class="layout-card-score">
                    <span class="score-num">${scores.axes.space_efficiency}</span>
                    <span class="score-label">Space</span>
                </div>
                <div class="layout-card-score">
                    <span class="score-num">${scores.axes.usability}</span>
                    <span class="score-label">Usability</span>
                </div>
                <div class="layout-card-score">
                    <span class="score-num">${scores.axes.daylight_comfort}</span>
                    <span class="score-label">Daylight</span>
                </div>
                <div class="layout-card-score">
                    <span class="score-num">${scores.axes.movement_flow}</span>
                    <span class="score-label">Flow</span>
                </div>
            </div>
            <div style="text-align:center;">
                <span style="font-family:var(--font-mono);font-size:1.2rem;font-weight:700;color:var(--accent-blue);">
                    ${scores.composite}
                </span>
                <span style="font-size:0.7rem;color:var(--text-muted);"> / 100</span>
            </div>
        `;
        card.appendChild(info);

        return card;
    },

    _getTransformFunctions(canvas, vertices) {
        const w = canvas.width;
        const h = canvas.height;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const v of vertices) {
            minX = Math.min(minX, v[0]); minY = Math.min(minY, v[1]);
            maxX = Math.max(maxX, v[0]); maxY = Math.max(maxY, v[1]);
        }

        const roomW = maxX - minX;
        const roomH = maxY - minY;
        const margin = w > 400 ? 40 : 15;
        const scaleX = (w - margin * 2) / roomW;
        const scaleY = (h - margin * 2) / roomH;
        const scale = Math.min(scaleX, scaleY);

        const offsetX = margin + (w - margin * 2 - roomW * scale) / 2;
        const offsetY = margin + (h - margin * 2 - roomH * scale) / 2;

        const tx = (x) => (x - minX) * scale + offsetX;
        const ty = (y) => (y - minY) * scale + offsetY;

        return { tx, ty, scale, minX, minY, maxX, maxY, roomW, roomH };
    },

    drawMiniLayout(canvas, layout, data) {
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        const isDark = !document.body.classList.contains('light-theme');

        ctx.fillStyle = isDark ? '#0a0a1a' : '#f5f5f5';
        ctx.fillRect(0, 0, w, h);

        const roomData = data.room || RoomCanvas.getRoomData();
        const vertices = roomData.vertices;
        if (!vertices || vertices.length < 3) return;

        const { tx, ty, scale } = this._getTransformFunctions(canvas, vertices);

        // Daylight zones
        if (data.daylight_zones) {
            for (const zone of data.daylight_zones) {
                if (zone.polygon && zone.polygon.length >= 3) {
                    ctx.beginPath();
                    ctx.moveTo(tx(zone.polygon[0][0]), ty(zone.polygon[0][1]));
                    for (let i = 1; i < zone.polygon.length; i++) {
                        ctx.lineTo(tx(zone.polygon[i][0]), ty(zone.polygon[i][1]));
                    }
                    ctx.closePath();
                    const alpha = zone.zone_type === 'primary' ? 0.08 : 0.04;
                    ctx.fillStyle = `rgba(255, 213, 79, ${alpha * zone.quality_score})`;
                    ctx.fill();
                }
            }
        }

        // Room polygon
        ctx.beginPath();
        ctx.moveTo(tx(vertices[0][0]), ty(vertices[0][1]));
        for (let i = 1; i < vertices.length; i++) {
            ctx.lineTo(tx(vertices[i][0]), ty(vertices[i][1]));
        }
        ctx.closePath();
        ctx.fillStyle = isDark ? 'rgba(37, 37, 64, 0.4)' : 'rgba(240, 240, 255, 0.6)';
        ctx.fill();
        ctx.strokeStyle = isDark ? '#4A90D9' : '#2a6cb8';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Doors
        for (const door of (roomData.doors || [])) {
            this._drawDoorSymbol(ctx, tx, ty, door, roomData, scale, isDark);
        }

        // Windows
        for (const win of (roomData.windows || [])) {
            this._drawWindowSymbol(ctx, tx, ty, win, roomData, scale, isDark);
        }

        // Furniture — use architectural symbols
        const theme = isDark ? 'dark' : 'light';
        for (const item of layout.placements) {
            FurnitureSymbols.draw(ctx, {
                ...item,
                cx: tx(item.x),
                cy: ty(item.y),
            }, scale, { showLabel: false, theme, strokeWidth: 0.8 });
        }
    },

    openDetail(layout, data) {
        this.currentLayout = layout;
        const modal = document.getElementById('layout-modal');
        modal.classList.remove('hidden');

        document.getElementById('modal-title').textContent = `Layout ${layout.layout_id} — Detail View`;

        // Draw large layout
        const canvas = document.getElementById('detail-canvas');
        canvas.width = 700;
        canvas.height = 500;
        this.drawDetailLayout(canvas, layout, data);

        // Score display
        const scores = layout.scores;
        document.getElementById('modal-score').textContent = scores.composite;

        const gradeEl = document.getElementById('modal-grade');
        gradeEl.textContent = scores.grade;
        gradeEl.className = 'score-grade';
        if (scores.grade.startsWith('A')) gradeEl.style.cssText = 'background:rgba(80,184,108,0.15);color:#50B86C;';
        else if (scores.grade.startsWith('B')) gradeEl.style.cssText = 'background:rgba(74,144,217,0.15);color:#4A90D9;';
        else if (scores.grade === 'C') gradeEl.style.cssText = 'background:rgba(232,131,58,0.15);color:#E8833A;';
        else gradeEl.style.cssText = 'background:rgba(231,76,60,0.15);color:#E74C3C;';

        this.drawRadarChart(scores.axes);
        this.drawFurnitureList(layout.placements);

        // Setup 3D toggle
        document.getElementById('three-container').classList.add('hidden');
        canvas.style.display = 'block';

        const btn3d = document.getElementById('btn-toggle-3d');
        btn3d.onclick = () => {
            const threeContainer = document.getElementById('three-container');
            if (threeContainer.classList.contains('hidden')) {
                threeContainer.classList.remove('hidden');
                canvas.style.display = 'none';
                btn3d.textContent = '2D View';
                IsometricView.render(layout, data);
            } else {
                threeContainer.classList.add('hidden');
                canvas.style.display = 'block';
                btn3d.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> 3D View';
                IsometricView.dispose();
            }
        };
    },

    drawDetailLayout(canvas, layout, data) {
        const ctx = canvas.getContext('2d');
        const w = canvas.width;
        const h = canvas.height;
        const isDark = !document.body.classList.contains('light-theme');

        ctx.fillStyle = isDark ? '#0a0a1a' : '#ffffff';
        ctx.fillRect(0, 0, w, h);

        const roomData = data.room || RoomCanvas.getRoomData();
        const vertices = roomData.vertices;
        if (!vertices || vertices.length < 3) return;

        const { tx, ty, scale, minX, minY, maxX, maxY } = this._getTransformFunctions(canvas, vertices);

        // Grid
        ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.06)';
        ctx.lineWidth = 0.5;
        const gridStep = 100;
        for (let gx = Math.floor(minX / gridStep) * gridStep; gx <= maxX; gx += gridStep) {
            ctx.beginPath();
            ctx.moveTo(tx(gx), ty(minY));
            ctx.lineTo(tx(gx), ty(maxY));
            ctx.stroke();
        }
        for (let gy = Math.floor(minY / gridStep) * gridStep; gy <= maxY; gy += gridStep) {
            ctx.beginPath();
            ctx.moveTo(tx(minX), ty(gy));
            ctx.lineTo(tx(maxX), ty(gy));
            ctx.stroke();
        }

        // Daylight zones
        if (data.daylight_zones) {
            for (const zone of data.daylight_zones) {
                if (zone.polygon && zone.polygon.length >= 3) {
                    ctx.beginPath();
                    ctx.moveTo(tx(zone.polygon[0][0]), ty(zone.polygon[0][1]));
                    for (let i = 1; i < zone.polygon.length; i++) {
                        ctx.lineTo(tx(zone.polygon[i][0]), ty(zone.polygon[i][1]));
                    }
                    ctx.closePath();
                    const alpha = zone.zone_type === 'primary' ? 0.12 : 0.06;
                    ctx.fillStyle = `rgba(255, 213, 79, ${alpha * zone.quality_score})`;
                    ctx.fill();
                }
            }
        }

        // Room polygon
        ctx.beginPath();
        ctx.moveTo(tx(vertices[0][0]), ty(vertices[0][1]));
        for (let i = 1; i < vertices.length; i++) {
            ctx.lineTo(tx(vertices[i][0]), ty(vertices[i][1]));
        }
        ctx.closePath();
        ctx.fillStyle = isDark ? 'rgba(37, 37, 64, 0.35)' : 'rgba(245, 245, 255, 0.8)';
        ctx.fill();
        ctx.strokeStyle = isDark ? '#4A90D9' : '#2a6cb8';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Wall dimensions
        ctx.font = '11px JetBrains Mono, monospace';
        ctx.fillStyle = isDark ? '#9898b8' : '#666';
        ctx.textAlign = 'center';
        for (let i = 0; i < vertices.length; i++) {
            const a = vertices[i];
            const b = vertices[(i + 1) % vertices.length];
            const mx = (tx(a[0]) + tx(b[0])) / 2;
            const my = (ty(a[1]) + ty(b[1])) / 2;
            const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
            ctx.fillText(`${(len / 100).toFixed(1)}m`, mx, my - 8);
        }

        // Doors with proper orientation
        for (const door of (roomData.doors || [])) {
            this._drawDoorSymbol(ctx, tx, ty, door, roomData, scale, isDark);
        }

        // Windows with wall alignment
        for (const win of (roomData.windows || [])) {
            this._drawWindowSymbol(ctx, tx, ty, win, roomData, scale, isDark);
        }

        // Furniture — architectural symbols
        const theme = isDark ? 'dark' : 'light';
        for (const item of layout.placements) {
            FurnitureSymbols.draw(ctx, {
                ...item,
                cx: tx(item.x),
                cy: ty(item.y),
            }, scale, { showLabel: true, labelSize: 9, theme, strokeWidth: 1 });
        }

        // Scale bar
        const scaleBarLen = 100 * scale;
        ctx.strokeStyle = isDark ? '#9898b8' : '#666';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(w - 55 - scaleBarLen, h - 15);
        ctx.lineTo(w - 55, h - 15);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(w - 55 - scaleBarLen, h - 18);
        ctx.lineTo(w - 55 - scaleBarLen, h - 12);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(w - 55, h - 18);
        ctx.lineTo(w - 55, h - 12);
        ctx.stroke();
        ctx.font = '10px JetBrains Mono';
        ctx.fillStyle = isDark ? '#9898b8' : '#666';
        ctx.textAlign = 'center';
        ctx.fillText('1m', w - 55 - scaleBarLen / 2, h - 4);
    },

    _drawDoorSymbol(ctx, tx, ty, door, roomData, scale, isDark) {
        const dx = tx(door.position[0]);
        const dy = ty(door.position[1]);
        const r = door.width * scale / 2;
        const vertices = roomData.vertices;

        // Find wall angle for proper door orientation
        let wallAngle = 0;
        const wi = door.wall_index;
        if (vertices && wi !== undefined && wi < vertices.length) {
            const a = vertices[wi];
            const b = vertices[(wi + 1) % vertices.length];
            wallAngle = Math.atan2(b[1] - a[1], b[0] - a[0]);
        }

        ctx.save();
        ctx.translate(dx, dy);
        ctx.rotate(wallAngle);

        // Door opening line on wall
        ctx.beginPath();
        ctx.moveTo(-r, 0);
        ctx.lineTo(r, 0);
        ctx.strokeStyle = isDark ? '#0a0a1a' : '#fff';
        ctx.lineWidth = 4;
        ctx.stroke();

        // Door swing arc
        ctx.beginPath();
        ctx.arc(r, 0, r * 2, Math.PI, Math.PI * 1.5);
        ctx.strokeStyle = isDark ? '#4FC3F7' : '#0288d1';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Door leaf line
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(r, -r * 2);
        ctx.strokeStyle = isDark ? '#4FC3F7' : '#0288d1';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.restore();
    },

    _drawWindowSymbol(ctx, tx, ty, win, roomData, scale, isDark) {
        const wx = tx(win.position[0]);
        const wy = ty(win.position[1]);
        const hw = win.width * scale / 2;
        const vertices = roomData.vertices;

        // Find wall angle
        let wallAngle = 0;
        const wi = win.wall_index;
        if (vertices && wi !== undefined && wi < vertices.length) {
            const a = vertices[wi];
            const b = vertices[(wi + 1) % vertices.length];
            wallAngle = Math.atan2(b[1] - a[1], b[0] - a[0]);
        }

        ctx.save();
        ctx.translate(wx, wy);
        ctx.rotate(wallAngle);

        // Window break in wall
        ctx.beginPath();
        ctx.moveTo(-hw, 0);
        ctx.lineTo(hw, 0);
        ctx.strokeStyle = isDark ? '#0a0a1a' : '#fff';
        ctx.lineWidth = 4;
        ctx.stroke();

        // Double parallel lines (window symbol)
        const offset = 2;
        ctx.beginPath();
        ctx.moveTo(-hw, -offset);
        ctx.lineTo(hw, -offset);
        ctx.strokeStyle = isDark ? '#FFD54F' : '#f9a825';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(-hw, offset);
        ctx.lineTo(hw, offset);
        ctx.stroke();

        // End caps
        ctx.beginPath();
        ctx.moveTo(-hw, -offset - 2);
        ctx.lineTo(-hw, offset + 2);
        ctx.strokeStyle = isDark ? '#FFD54F' : '#f9a825';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(hw, -offset - 2);
        ctx.lineTo(hw, offset + 2);
        ctx.stroke();

        ctx.restore();
    },

    drawRadarChart(axes) {
        const canvas = document.getElementById('radar-chart');

        if (this.radarChart) {
            this.radarChart.destroy();
        }

        const isDark = !document.body.classList.contains('light-theme');

        this.radarChart = new Chart(canvas, {
            type: 'radar',
            data: {
                labels: ['Space Efficiency', 'Usability', 'Daylight Comfort', 'Movement Flow'],
                datasets: [{
                    data: [axes.space_efficiency, axes.usability, axes.daylight_comfort, axes.movement_flow],
                    backgroundColor: 'rgba(74, 144, 217, 0.15)',
                    borderColor: '#4A90D9',
                    borderWidth: 2,
                    pointBackgroundColor: '#4A90D9',
                    pointBorderColor: isDark ? '#fff' : '#333',
                    pointBorderWidth: 1,
                    pointRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 25,
                            color: isDark ? '#6868a0' : '#999',
                            backdropColor: 'transparent',
                            font: { size: 9, family: 'JetBrains Mono' },
                        },
                        grid: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)' },
                        angleLines: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)' },
                        pointLabels: {
                            color: isDark ? '#9898b8' : '#555',
                            font: { size: 10, family: 'Inter' },
                        },
                    },
                },
            },
        });
    },

    drawFurnitureList(placements) {
        const container = document.getElementById('modal-furniture-list');
        container.innerHTML = '<h4>Furniture Placements</h4>';

        const grouped = {};
        for (const p of placements) {
            const key = p.name || p.category;
            if (!grouped[key]) grouped[key] = { ...p, count: 0 };
            grouped[key].count++;
        }

        for (const [name, item] of Object.entries(grouped)) {
            const div = document.createElement('div');
            div.className = 'modal-furn-item';
            div.innerHTML = `
                <div class="modal-furn-color" style="background:${item.color}"></div>
                <span class="modal-furn-name">${name}</span>
                <span class="modal-furn-pos">×${item.count}</span>
            `;
            container.appendChild(div);
        }
    },

    closeResults() {
        document.getElementById('results-panel').classList.add('hidden');
        document.getElementById('app-main').style.height = 'calc(100vh - 56px)';
    },

    closeModal() {
        document.getElementById('layout-modal').classList.add('hidden');
        IsometricView.dispose();
    },
};
