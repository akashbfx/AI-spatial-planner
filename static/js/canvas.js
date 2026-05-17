/**
 * Room Drawing Canvas — Fabric.js interactive room editor with CAD features.
 * Supports wall editing, door/window orientation, select mode, and measure tool.
 */

const RoomCanvas = {
    canvas: null,
    mode: 'draw_walls',  // draw_walls, add_door, add_window, select, measure, edit_wall
    isDrawing: false,
    wallPoints: [],
    roomClosed: false,

    // Room data
    walls: [],
    doors: [],
    windows: [],

    // Selection state
    selectedElement: null,
    selectedType: null,
    dragTarget: null,
    dragStartPos: null,

    // Measure tool state
    measureStart: null,
    measureLine: null,

    // Colors
    COLORS: {
        wall: '#4A90D9',
        wallFill: 'rgba(37, 37, 64, 0.4)',
        door: '#4FC3F7',
        window: '#FFD54F',
        grid: 'rgba(255,255,255,0.04)',
        gridMajor: 'rgba(255,255,255,0.08)',
        point: '#6B4DE6',
        pointHover: '#9B59B6',
        pointSelected: '#E74C3C',
        dimension: '#9898b8',
        measure: '#50B86C',
        selection: '#FFD54F',
    },

    GRID_SIZE: 20,
    SCALE: 0.7,
    snapGrid: 10, // snap to 10cm

    init() {
        const container = document.getElementById('canvas-container');
        const w = container.clientWidth;
        const h = container.clientHeight;

        this.canvas = new fabric.Canvas('room-canvas', {
            width: w,
            height: h,
            backgroundColor: document.body.classList.contains('light-theme') ? '#f0f0f5' : '#0a0a1a',
            selection: false,
        });

        this.drawGrid();
        this.bindEvents();
        this.updateInfo();

        window.addEventListener('resize', Utils.debounce(() => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            this.canvas.setDimensions({ width: w, height: h });
            this.drawGrid();
            this.redrawRoom();
        }, 200));
    },

    updateTheme() {
        const isDark = !document.body.classList.contains('light-theme');
        this.canvas.backgroundColor = isDark ? '#0a0a1a' : '#f0f0f5';

        this.COLORS.grid = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)';
        this.COLORS.gridMajor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
        this.COLORS.wallFill = isDark ? 'rgba(37, 37, 64, 0.4)' : 'rgba(220, 220, 240, 0.5)';
        this.COLORS.dimension = isDark ? '#9898b8' : '#666';

        this.drawGrid();
        this.redrawRoom();
    },

    drawGrid() {
        this.canvas.getObjects('line').forEach(obj => {
            if (obj._isGrid) this.canvas.remove(obj);
        });

        const w = this.canvas.width;
        const h = this.canvas.height;
        const step = this.GRID_SIZE;

        for (let x = 0; x < w; x += step) {
            const isMajor = (x % (step * 5)) === 0;
            const line = new fabric.Line([x, 0, x, h], {
                stroke: isMajor ? this.COLORS.gridMajor : this.COLORS.grid,
                strokeWidth: isMajor ? 0.5 : 0.3,
                selectable: false,
                evented: false,
                _isGrid: true,
            });
            this.canvas.add(line);
            this.canvas.sendToBack(line);
        }
        for (let y = 0; y < h; y += step) {
            const isMajor = (y % (step * 5)) === 0;
            const line = new fabric.Line([0, y, w, y], {
                stroke: isMajor ? this.COLORS.gridMajor : this.COLORS.grid,
                strokeWidth: isMajor ? 0.5 : 0.3,
                selectable: false,
                evented: false,
                _isGrid: true,
            });
            this.canvas.add(line);
            this.canvas.sendToBack(line);
        }
    },

    canvasToRoom(x, y) {
        const offset = this.getOffset();
        return {
            x: Math.round((x - offset.x) / this.SCALE),
            y: Math.round((y - offset.y) / this.SCALE),
        };
    },

    roomToCanvas(x, y) {
        const offset = this.getOffset();
        return {
            x: x * this.SCALE + offset.x,
            y: y * this.SCALE + offset.y,
        };
    },

    getOffset() {
        return {
            x: this.canvas.width * 0.1,
            y: this.canvas.height * 0.1,
        };
    },

    snapToGrid(val) {
        return Utils.snap(val, this.snapGrid);
    },

    bindEvents() {
        const self = this;

        this.canvas.on('mouse:down', function(opt) {
            const pointer = self.canvas.getPointer(opt.e);

            if (self.mode === 'draw_walls' && !self.roomClosed) {
                const room = self.canvasToRoom(pointer.x, pointer.y);
                room.x = self.snapToGrid(room.x);
                room.y = self.snapToGrid(room.y);

                if (self.wallPoints.length >= 3) {
                    const first = self.wallPoints[0];
                    const dist = Math.hypot(room.x - first.x, room.y - first.y);
                    if (dist < 30) {
                        self.wallPoints.push({ x: first.x, y: first.y });
                        self.roomClosed = true;
                        self.finalizeRoom();
                        return;
                    }
                }

                self.wallPoints.push(room);
                self.redrawRoom();

            } else if (self.mode === 'add_door' && self.roomClosed) {
                const room = self.canvasToRoom(pointer.x, pointer.y);
                self.addDoorAtPoint(room.x, room.y);

            } else if (self.mode === 'add_window' && self.roomClosed) {
                const room = self.canvasToRoom(pointer.x, pointer.y);
                self.addWindowAtPoint(room.x, room.y);

            } else if (self.mode === 'select') {
                self.handleSelect(pointer);

            } else if (self.mode === 'edit_wall') {
                self.handleWallEdit(pointer, opt.e);

            } else if (self.mode === 'measure') {
                const room = self.canvasToRoom(pointer.x, pointer.y);
                if (!self.measureStart) {
                    self.measureStart = room;
                    Utils.toast('Click second point to measure', 'info');
                } else {
                    const dist = Math.hypot(room.x - self.measureStart.x, room.y - self.measureStart.y);
                    Utils.toast(`Distance: ${(dist / 100).toFixed(2)}m (${Math.round(dist)}cm)`, 'success');
                    self.removeMeasureLine();
                    self.measureStart = null;
                }
                self.redrawRoom();
            }
        });

        this.canvas.on('mouse:move', function(opt) {
            const pointer = self.canvas.getPointer(opt.e);
            const room = self.canvasToRoom(pointer.x, pointer.y);
            document.getElementById('cursor-position').textContent =
                `x: ${Math.round(room.x)} y: ${Math.round(room.y)} cm`;

            // Measure tool preview
            if (self.mode === 'measure' && self.measureStart) {
                self.drawMeasurePreview(pointer);
            }

            // Drag handling for select/edit modes
            if (self.dragTarget && self.mode === 'edit_wall') {
                self.handleWallDrag(pointer);
            }
        });

        this.canvas.on('mouse:up', function() {
            self.dragTarget = null;
        });

        // Tool buttons
        document.getElementById('btn-draw-walls').addEventListener('click', () => self.setMode('draw_walls'));
        document.getElementById('btn-add-door').addEventListener('click', () => self.setMode('add_door'));
        document.getElementById('btn-add-window').addEventListener('click', () => self.setMode('add_window'));
        document.getElementById('btn-clear-canvas').addEventListener('click', () => self.clearAll());
        document.getElementById('btn-undo').addEventListener('click', () => self.undo());

        // New tool buttons (if they exist)
        const btnSelect = document.getElementById('btn-select');
        const btnEditWall = document.getElementById('btn-edit-wall');
        const btnMeasure = document.getElementById('btn-measure');

        if (btnSelect) btnSelect.addEventListener('click', () => self.setMode('select'));
        if (btnEditWall) btnEditWall.addEventListener('click', () => self.setMode('edit_wall'));
        if (btnMeasure) btnMeasure.addEventListener('click', () => self.setMode('measure'));

        // Snap grid selector
        const snapSelect = document.getElementById('snap-grid-select');
        if (snapSelect) {
            snapSelect.addEventListener('change', (e) => {
                self.snapGrid = parseInt(e.target.value) || 10;
                Utils.toast(`Snap: ${self.snapGrid}cm`, 'info');
            });
        }
    },

    setMode(mode) {
        this.mode = mode;
        this.selectedElement = null;
        this.measureStart = null;
        this.removeMeasureLine();

        document.querySelectorAll('.canvas-tools .tool-btn').forEach(btn => btn.classList.remove('active'));

        const btnMap = {
            'draw_walls': 'btn-draw-walls',
            'add_door': 'btn-add-door',
            'add_window': 'btn-add-window',
            'select': 'btn-select',
            'edit_wall': 'btn-edit-wall',
            'measure': 'btn-measure',
        };
        const btn = document.getElementById(btnMap[mode]);
        if (btn) btn.classList.add('active');

        const toasts = {
            'add_door': 'Click on a wall to place a door',
            'add_window': 'Click on a wall to place a window',
            'select': 'Click on a door or window to select and edit',
            'edit_wall': 'Click and drag wall vertices to edit',
            'measure': 'Click two points to measure distance',
        };
        if (toasts[mode]) Utils.toast(toasts[mode], 'info');

        this.redrawRoom();
    },

    // ─── Wall Editing ────────────────────────────────────────────

    handleWallEdit(pointer, event) {
        if (!this.roomClosed || this.walls.length < 3) return;

        const room = this.canvasToRoom(pointer.x, pointer.y);

        // Check if clicking near a vertex
        for (let i = 0; i < this.walls.length; i++) {
            const dist = Math.hypot(room.x - this.walls[i][0], room.y - this.walls[i][1]);
            if (dist < 20) {
                // Right-click to delete vertex
                if (event && event.button === 2 && this.walls.length > 3) {
                    this.walls.splice(i, 1);
                    // Update door/window wall indices
                    this.doors = this.doors.filter(d => {
                        if (d.wall_index >= i) d.wall_index = Math.max(0, d.wall_index - 1);
                        return true;
                    });
                    this.windows = this.windows.filter(w => {
                        if (w.wall_index >= i) w.wall_index = Math.max(0, w.wall_index - 1);
                        return true;
                    });
                    this.redrawRoom();
                    this.updateInfo();
                    Utils.toast('Vertex deleted', 'info');
                    return;
                }

                // Left-click to start dragging
                this.dragTarget = { type: 'vertex', index: i };
                return;
            }
        }

        // Check if clicking on wall segment midpoint — add vertex
        for (let i = 0; i < this.walls.length; i++) {
            const a = this.walls[i];
            const b = this.walls[(i + 1) % this.walls.length];
            const mx = (a[0] + b[0]) / 2;
            const my = (a[1] + b[1]) / 2;
            const dist = Math.hypot(room.x - mx, room.y - my);
            if (dist < 25) {
                // Insert new vertex at midpoint
                const newPoint = [this.snapToGrid(mx), this.snapToGrid(my)];
                this.walls.splice(i + 1, 0, newPoint);
                // Update door/window wall indices
                this.doors.forEach(d => {
                    if (d.wall_index > i) d.wall_index++;
                });
                this.windows.forEach(w => {
                    if (w.wall_index > i) w.wall_index++;
                });
                this.redrawRoom();
                this.updateInfo();
                Utils.toast('Vertex added — drag to reposition', 'success');
                this.dragTarget = { type: 'vertex', index: i + 1 };
                return;
            }
        }
    },

    handleWallDrag(pointer) {
        if (!this.dragTarget || this.dragTarget.type !== 'vertex') return;

        const room = this.canvasToRoom(pointer.x, pointer.y);
        const idx = this.dragTarget.index;
        this.walls[idx] = [this.snapToGrid(room.x), this.snapToGrid(room.y)];
        this.redrawRoom();
        this.updateInfo();
    },

    // ─── Selection ───────────────────────────────────────────────

    handleSelect(pointer) {
        const room = this.canvasToRoom(pointer.x, pointer.y);

        // Check doors
        for (let i = 0; i < this.doors.length; i++) {
            const door = this.doors[i];
            const dist = Math.hypot(room.x - door.position[0], room.y - door.position[1]);
            if (dist < 40) {
                this.selectedElement = i;
                this.selectedType = 'door';
                this.redrawRoom();
                this.showElementProperties('door', door, i);
                return;
            }
        }

        // Check windows
        for (let i = 0; i < this.windows.length; i++) {
            const win = this.windows[i];
            const dist = Math.hypot(room.x - win.position[0], room.y - win.position[1]);
            if (dist < 40) {
                this.selectedElement = i;
                this.selectedType = 'window';
                this.redrawRoom();
                this.showElementProperties('window', win, i);
                return;
            }
        }

        // Deselect
        this.selectedElement = null;
        this.selectedType = null;
        this.hideElementProperties();
        this.redrawRoom();
    },

    showElementProperties(type, element, index) {
        const propsPanel = document.getElementById('element-properties');
        if (!propsPanel) return;

        propsPanel.classList.remove('hidden');
        let html = '';

        if (type === 'door') {
            html = `
                <h4>🚪 Door ${index + 1}</h4>
                <div class="input-group">
                    <label>Width (cm)</label>
                    <input type="number" value="${element.width}" min="60" max="200" step="10"
                        onchange="RoomCanvas.updateElement('door', ${index}, 'width', this.value)">
                </div>
                <div class="input-group">
                    <label>Swing</label>
                    <select onchange="RoomCanvas.updateElement('door', ${index}, 'swing', this.value)">
                        <option value="inward" ${element.swing === 'inward' ? 'selected' : ''}>Inward</option>
                        <option value="outward" ${element.swing === 'outward' ? 'selected' : ''}>Outward</option>
                    </select>
                </div>
                <button class="btn-danger-small" onclick="RoomCanvas.deleteElement('door', ${index})">Delete Door</button>
            `;
        } else {
            html = `
                <h4>🪟 Window ${index + 1}</h4>
                <div class="input-group">
                    <label>Width (cm)</label>
                    <input type="number" value="${element.width}" min="40" max="400" step="10"
                        onchange="RoomCanvas.updateElement('window', ${index}, 'width', this.value)">
                </div>
                <div class="input-group">
                    <label>Sill Height (cm)</label>
                    <input type="number" value="${element.sill_height}" min="0" max="200" step="10"
                        onchange="RoomCanvas.updateElement('window', ${index}, 'sill_height', this.value)">
                </div>
                <div class="input-group">
                    <label>Head Height (cm)</label>
                    <input type="number" value="${element.head_height}" min="100" max="300" step="10"
                        onchange="RoomCanvas.updateElement('window', ${index}, 'head_height', this.value)">
                </div>
                <button class="btn-danger-small" onclick="RoomCanvas.deleteElement('window', ${index})">Delete Window</button>
            `;
        }

        propsPanel.innerHTML = html;
    },

    hideElementProperties() {
        const propsPanel = document.getElementById('element-properties');
        if (propsPanel) propsPanel.classList.add('hidden');
    },

    updateElement(type, index, prop, value) {
        const val = parseFloat(value) || 0;
        if (type === 'door' && this.doors[index]) {
            this.doors[index][prop] = val;
        } else if (type === 'window' && this.windows[index]) {
            this.windows[index][prop] = val;
        }
        this.redrawRoom();
    },

    deleteElement(type, index) {
        if (type === 'door') {
            this.doors.splice(index, 1);
            ConfigPanel.updateDoorsList();
        } else {
            this.windows.splice(index, 1);
            ConfigPanel.updateWindowsList();
        }
        this.selectedElement = null;
        this.hideElementProperties();
        this.redrawRoom();
        this.updateInfo();
        Utils.toast(`${type === 'door' ? 'Door' : 'Window'} deleted`, 'info');
    },

    // ─── Measure Tool ────────────────────────────────────────────

    drawMeasurePreview(pointer) {
        this.removeMeasureLine();
        if (!this.measureStart) return;

        const start = this.roomToCanvas(this.measureStart.x, this.measureStart.y);
        const room = this.canvasToRoom(pointer.x, pointer.y);
        const dist = Math.hypot(room.x - this.measureStart.x, room.y - this.measureStart.y);

        const line = new fabric.Line([start.x, start.y, pointer.x, pointer.y], {
            stroke: this.COLORS.measure,
            strokeWidth: 1.5,
            strokeDashArray: [6, 4],
            selectable: false,
            evented: false,
            _isMeasure: true,
        });
        this.canvas.add(line);

        const mx = (start.x + pointer.x) / 2;
        const my = (start.y + pointer.y) / 2;
        const label = new fabric.Text(`${(dist / 100).toFixed(2)}m`, {
            left: mx,
            top: my - 16,
            fontSize: 12,
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 'bold',
            fill: this.COLORS.measure,
            textAlign: 'center',
            originX: 'center',
            backgroundColor: 'rgba(0,0,0,0.6)',
            padding: 3,
            selectable: false,
            evented: false,
            _isMeasure: true,
        });
        this.canvas.add(label);
        this.canvas.renderAll();
    },

    removeMeasureLine() {
        this.canvas.getObjects().forEach(obj => {
            if (obj._isMeasure) this.canvas.remove(obj);
        });
    },

    // ─── Core Drawing ────────────────────────────────────────────

    finalizeRoom() {
        this.walls = this.wallPoints.slice(0, -1).map(p => [p.x, p.y]);
        this.redrawRoom();
        this.setMode('add_door');
        Utils.toast('Room created! Now add doors and windows.', 'success');
        this.updateInfo();
    },

    addDoorAtPoint(rx, ry) {
        const closest = this.findClosestWall(rx, ry);
        if (!closest || closest.dist > 50) {
            Utils.toast('Click closer to a wall to place a door', 'warning');
            return;
        }

        const door = {
            position: [closest.projX, closest.projY],
            width: 90,
            wall_index: closest.wallIndex,
            swing: 'inward',
            id: Utils.uid(),
        };

        this.doors.push(door);
        this.redrawRoom();
        Utils.toast('Door added', 'success');
        ConfigPanel.updateDoorsList();
        this.updateInfo();
    },

    addWindowAtPoint(rx, ry) {
        const closest = this.findClosestWall(rx, ry);
        if (!closest || closest.dist > 50) {
            Utils.toast('Click closer to a wall to place a window', 'warning');
            return;
        }

        const win = {
            position: [closest.projX, closest.projY],
            width: 120,
            wall_index: closest.wallIndex,
            sill_height: 90,
            head_height: 210,
            id: Utils.uid(),
        };

        this.windows.push(win);
        this.redrawRoom();
        Utils.toast('Window added', 'success');
        ConfigPanel.updateWindowsList();
        this.updateInfo();
    },

    findClosestWall(rx, ry) {
        if (this.walls.length < 2) return null;

        let best = null;
        for (let i = 0; i < this.walls.length; i++) {
            const a = this.walls[i];
            const b = this.walls[(i + 1) % this.walls.length];

            const dx = b[0] - a[0];
            const dy = b[1] - a[1];
            const len = Math.hypot(dx, dy);
            if (len === 0) continue;

            let t = ((rx - a[0]) * dx + (ry - a[1]) * dy) / (len * len);
            t = Math.max(0.05, Math.min(0.95, t));

            const projX = a[0] + t * dx;
            const projY = a[1] + t * dy;
            const dist = Math.hypot(rx - projX, ry - projY);

            if (!best || dist < best.dist) {
                best = { dist, projX: Math.round(projX), projY: Math.round(projY), wallIndex: i, t };
            }
        }
        return best;
    },

    redrawRoom() {
        // Remove old room objects
        this.canvas.getObjects().forEach(obj => {
            if (obj._isRoom) this.canvas.remove(obj);
        });

        if (this.wallPoints.length < 2 && this.walls.length === 0) return;

        const points = this.walls.length > 0
            ? this.walls.map(w => ({ x: w[0], y: w[1] }))
            : this.wallPoints;

        const isDark = !document.body.classList.contains('light-theme');

        // Draw room polygon fill
        if (this.roomClosed && points.length >= 3) {
            const canvasPoints = points.map(p => this.roomToCanvas(p.x || p[0], p.y || p[1]));
            const polygon = new fabric.Polygon(canvasPoints, {
                fill: this.COLORS.wallFill,
                stroke: this.COLORS.wall,
                strokeWidth: 2.5,
                selectable: false,
                evented: false,
                _isRoom: true,
            });
            this.canvas.add(polygon);
        }

        // Draw wall segments
        for (let i = 0; i < points.length; i++) {
            const a = points[i];
            const b = points[(i + 1) % points.length];
            if (!this.roomClosed && i === points.length - 1) break;

            const ca = this.roomToCanvas(a.x !== undefined ? a.x : a[0], a.y !== undefined ? a.y : a[1]);
            const cb = this.roomToCanvas(b.x !== undefined ? b.x : b[0], b.y !== undefined ? b.y : b[1]);

            const line = new fabric.Line([ca.x, ca.y, cb.x, cb.y], {
                stroke: this.COLORS.wall,
                strokeWidth: 3,
                selectable: false,
                evented: false,
                _isRoom: true,
            });
            this.canvas.add(line);

            // Dimension label
            const mx = (ca.x + cb.x) / 2;
            const my = (ca.y + cb.y) / 2;
            const ax = (a.x !== undefined ? a.x : a[0]);
            const ay = (a.y !== undefined ? a.y : a[1]);
            const bx = (b.x !== undefined ? b.x : b[0]);
            const by = (b.y !== undefined ? b.y : b[1]);
            const len = Math.hypot(bx - ax, by - ay);
            const label = new fabric.Text(`${(len / 100).toFixed(1)}m`, {
                left: mx,
                top: my - 14,
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
                fill: this.COLORS.dimension,
                textAlign: 'center',
                originX: 'center',
                selectable: false,
                evented: false,
                _isRoom: true,
            });
            this.canvas.add(label);

            // Wall midpoint indicator for edit mode
            if (this.mode === 'edit_wall' && this.roomClosed) {
                const midC = this.roomToCanvas((ax + bx) / 2, (ay + by) / 2);
                const midDot = new fabric.Circle({
                    left: midC.x - 3,
                    top: midC.y - 3,
                    radius: 3,
                    fill: this.COLORS.measure,
                    stroke: '#fff',
                    strokeWidth: 0.5,
                    opacity: 0.6,
                    selectable: false,
                    evented: false,
                    _isRoom: true,
                });
                this.canvas.add(midDot);
            }
        }

        // Draw corner points
        for (let pi = 0; pi < points.length; pi++) {
            const p = points[pi];
            const c = this.roomToCanvas(p.x !== undefined ? p.x : p[0], p.y !== undefined ? p.y : p[1]);
            const isEditing = this.mode === 'edit_wall';
            const r = isEditing ? 6 : 4;
            const color = isEditing
                ? (this.dragTarget && this.dragTarget.index === pi ? this.COLORS.pointSelected : this.COLORS.pointHover)
                : this.COLORS.point;

            const circle = new fabric.Circle({
                left: c.x - r,
                top: c.y - r,
                radius: r,
                fill: color,
                stroke: '#fff',
                strokeWidth: 1,
                selectable: false,
                evented: false,
                _isRoom: true,
            });
            this.canvas.add(circle);
        }

        // Draw doors with proper wall-aligned orientation
        for (let di = 0; di < this.doors.length; di++) {
            const door = this.doors[di];
            const isSelected = this.selectedType === 'door' && this.selectedElement === di;
            this._drawDoorOnCanvas(door, isSelected);
        }

        // Draw windows with wall alignment
        for (let wi = 0; wi < this.windows.length; wi++) {
            const win = this.windows[wi];
            const isSelected = this.selectedType === 'window' && this.selectedElement === wi;
            this._drawWindowOnCanvas(win, isSelected);
        }

        // Measure start point indicator
        if (this.measureStart) {
            const mc = this.roomToCanvas(this.measureStart.x, this.measureStart.y);
            const dot = new fabric.Circle({
                left: mc.x - 4,
                top: mc.y - 4,
                radius: 4,
                fill: this.COLORS.measure,
                stroke: '#fff',
                strokeWidth: 1,
                selectable: false,
                evented: false,
                _isRoom: true,
            });
            this.canvas.add(dot);
        }

        this.canvas.renderAll();
    },

    _drawDoorOnCanvas(door, isSelected) {
        const c = this.roomToCanvas(door.position[0], door.position[1]);
        const hw = (door.width / 2) * this.SCALE;

        // Calculate wall angle for proper orientation
        let wallAngle = 0;
        const wi = door.wall_index;
        if (this.walls.length > wi) {
            const a = this.walls[wi];
            const b = this.walls[(wi + 1) % this.walls.length];
            wallAngle = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
        }

        // Calculate inward perpendicular direction
        let perpAngle = wallAngle + 90;

        // Create a group for the door
        const strokeColor = isSelected ? this.COLORS.selection : this.COLORS.door;

        // Door opening (gap in wall)
        const gap = new fabric.Line([-hw, 0, hw, 0], {
            stroke: this.canvas.backgroundColor,
            strokeWidth: 5,
            selectable: false,
            evented: false,
        });

        // Door leaf line
        const leafLen = door.width * this.SCALE;
        const leaf = new fabric.Line([hw, 0, hw, -leafLen], {
            stroke: strokeColor,
            strokeWidth: 1.5,
            selectable: false,
            evented: false,
        });

        // Door swing arc
        const arc = new fabric.Circle({
            left: hw - leafLen,
            top: -leafLen,
            radius: leafLen,
            fill: 'transparent',
            stroke: strokeColor,
            strokeWidth: 1,
            startAngle: 270,
            endAngle: 360,
            selectable: false,
            evented: false,
        });

        const group = new fabric.Group([gap, leaf, arc], {
            left: c.x,
            top: c.y,
            originX: 'center',
            originY: 'center',
            angle: wallAngle,
            selectable: false,
            evented: false,
            _isRoom: true,
        });

        this.canvas.add(group);

        // Door label
        const dlabel = new fabric.Text('D', {
            left: c.x,
            top: c.y + 14,
            fontSize: 10,
            fontFamily: 'Inter, sans-serif',
            fontWeight: 'bold',
            fill: strokeColor,
            originX: 'center',
            selectable: false,
            evented: false,
            _isRoom: true,
        });
        this.canvas.add(dlabel);
    },

    _drawWindowOnCanvas(win, isSelected) {
        const c = this.roomToCanvas(win.position[0], win.position[1]);
        const hw = (win.width / 2) * this.SCALE;

        // Wall angle for orientation
        const wi = win.wall_index;
        let angle = 0;
        if (this.walls.length > wi) {
            const a = this.walls[wi];
            const b = this.walls[(wi + 1) % this.walls.length];
            angle = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
        }

        const strokeColor = isSelected ? this.COLORS.selection : this.COLORS.window;

        // Double parallel lines (architectural window symbol)
        const offset = 3;
        const wline1 = new fabric.Line([-hw, -offset, hw, -offset], {
            stroke: strokeColor,
            strokeWidth: 1.5,
            selectable: false,
            evented: false,
        });
        const wline2 = new fabric.Line([-hw, offset, hw, offset], {
            stroke: strokeColor,
            strokeWidth: 1.5,
            selectable: false,
            evented: false,
        });
        // End caps
        const cap1 = new fabric.Line([-hw, -offset - 2, -hw, offset + 2], {
            stroke: strokeColor,
            strokeWidth: 1,
            selectable: false,
            evented: false,
        });
        const cap2 = new fabric.Line([hw, -offset - 2, hw, offset + 2], {
            stroke: strokeColor,
            strokeWidth: 1,
            selectable: false,
            evented: false,
        });

        const group = new fabric.Group([wline1, wline2, cap1, cap2], {
            left: c.x,
            top: c.y,
            originX: 'center',
            originY: 'center',
            angle: angle,
            selectable: false,
            evented: false,
            _isRoom: true,
        });
        this.canvas.add(group);
    },

    // ─── Presets, Export, etc. ────────────────────────────────────

    loadPreset(preset) {
        this.clearAll(false);
        this.walls = preset.vertices.map(v => [v[0], v[1]]);
        this.roomClosed = true;

        const bounds = this.getBounds();
        const cw = this.canvas.width * 0.75;
        const ch = this.canvas.height * 0.75;
        const scaleX = cw / (bounds.maxX - bounds.minX);
        const scaleY = ch / (bounds.maxY - bounds.minY);
        this.SCALE = Math.min(scaleX, scaleY, 1.0);

        this.doors = (preset.doors || []).map(d => ({ ...d, id: Utils.uid() }));
        this.windows = (preset.windows || []).map(w => ({ ...w, id: Utils.uid() }));

        this.redrawRoom();
        this.updateInfo();

        const widthM = (bounds.maxX - bounds.minX) / 100;
        const heightM = (bounds.maxY - bounds.minY) / 100;
        document.getElementById('room-width').value = widthM.toFixed(1);
        document.getElementById('room-height').value = heightM.toFixed(1);

        ConfigPanel.updateDoorsList();
        ConfigPanel.updateWindowsList();
        Utils.toast(`Loaded: ${preset.name}`, 'success');
    },

    loadRectRoom(widthM, heightM) {
        this.clearAll(false);
        const w = widthM * 100;
        const h = heightM * 100;

        this.walls = [[0, 0], [w, 0], [w, h], [0, h]];
        this.roomClosed = true;

        const cw = this.canvas.width * 0.7;
        const ch = this.canvas.height * 0.7;
        this.SCALE = Math.min(cw / w, ch / h, 1.0);

        this.redrawRoom();
        this.updateInfo();
        Utils.toast(`Room set: ${widthM}m × ${heightM}m`, 'success');
    },

    getBounds() {
        if (this.walls.length === 0) return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const w of this.walls) {
            minX = Math.min(minX, w[0]);
            minY = Math.min(minY, w[1]);
            maxX = Math.max(maxX, w[0]);
            maxY = Math.max(maxY, w[1]);
        }
        return { minX, minY, maxX, maxY };
    },

    getRoomData() {
        return {
            vertices: this.walls,
            doors: this.doors.map(d => ({
                position: d.position,
                width: d.width,
                wall_index: d.wall_index,
                swing: d.swing || 'inward',
            })),
            windows: this.windows.map(w => ({
                position: w.position,
                width: w.width,
                wall_index: w.wall_index,
                sill_height: w.sill_height || 90,
                head_height: w.head_height || 210,
            })),
        };
    },

    updateInfo() {
        const bounds = this.getBounds();
        const w = bounds.maxX - bounds.minX;
        const h = bounds.maxY - bounds.minY;
        document.getElementById('canvas-dimensions').textContent =
            `${(w / 100).toFixed(1)} × ${(h / 100).toFixed(1)} m`;

        let area = 0;
        const n = this.walls.length;
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += this.walls[i][0] * this.walls[j][1];
            area -= this.walls[j][0] * this.walls[i][1];
        }
        area = Math.abs(area) / 2;
        document.getElementById('canvas-area').textContent =
            `${(area / 10000).toFixed(1)} sqm`;
    },

    clearAll(showToast = true) {
        this.wallPoints = [];
        this.walls = [];
        this.doors = [];
        this.windows = [];
        this.roomClosed = false;
        this.SCALE = 0.7;
        this.selectedElement = null;
        this.measureStart = null;

        this.canvas.getObjects().forEach(obj => {
            if (obj._isRoom || obj._isMeasure) this.canvas.remove(obj);
        });
        this.canvas.renderAll();
        this.updateInfo();
        this.hideElementProperties();

        if (showToast) {
            Utils.toast('Canvas cleared', 'info');
            ConfigPanel.updateDoorsList();
            ConfigPanel.updateWindowsList();
        }
    },

    undo() {
        if (this.windows.length > 0) {
            this.windows.pop();
            ConfigPanel.updateWindowsList();
        } else if (this.doors.length > 0) {
            this.doors.pop();
            ConfigPanel.updateDoorsList();
        } else if (!this.roomClosed && this.wallPoints.length > 0) {
            this.wallPoints.pop();
        } else if (this.roomClosed) {
            this.roomClosed = false;
            this.wallPoints = this.walls.map(w => ({ x: w[0], y: w[1] }));
            this.walls = [];
        }
        this.redrawRoom();
        this.updateInfo();
    },
};
