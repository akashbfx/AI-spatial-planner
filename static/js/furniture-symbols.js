/**
 * Furniture Symbols — Architectural plan-view symbols for furniture rendering.
 * Draws proper CAD-style symbols instead of colored boxes.
 */

const FurnitureSymbols = {

    /**
     * Draw a furniture item using its architectural symbol.
     * @param {CanvasRenderingContext2D} ctx
     * @param {Object} item — { x, y, width, depth, rotation, category, color, name }
     * @param {number} scale — pixels per cm
     * @param {Object} opts — { showLabel, labelSize, strokeWidth, theme }
     */
    draw(ctx, item, scale, opts = {}) {
        const {
            showLabel = true,
            labelSize = 9,
            strokeWidth = 1,
            theme = 'dark',
        } = opts;

        const cx = item.cx || 0;  // pre-transformed center x
        const cy = item.cy || 0;  // pre-transformed center y
        const fw = item.width * scale;
        const fd = item.depth * scale;
        const color = item.color || '#888';
        const rot = (item.rotation || 0) * Math.PI / 180;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rot);

        const fillCol = theme === 'light' ? '#ffffff' : 'rgba(30,30,50,0.7)';
        const strokeCol = theme === 'light' ? '#333333' : color;
        const textCol = theme === 'light' ? '#333333' : 'rgba(255,255,255,0.85)';

        ctx.lineWidth = strokeWidth;
        ctx.strokeStyle = strokeCol;
        ctx.fillStyle = fillCol;

        switch (item.category) {
            case 'work_desk':
                this._drawDesk(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'chair':
                this._drawChair(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'meeting_table':
                this._drawMeetingTable(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'shared_table':
                this._drawSharedTable(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'storage':
                this._drawStorage(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'collaborative_seating':
                this._drawBench(ctx, fw, fd, strokeCol, fillCol);
                break;
            case 'lounge':
                this._drawLounge(ctx, fw, fd, strokeCol, fillCol);
                break;
            default:
                this._drawGeneric(ctx, fw, fd, strokeCol, fillCol);
        }

        // Label
        if (showLabel && fw > 20 && fd > 12) {
            ctx.fillStyle = textCol;
            const fSize = Math.min(labelSize, fw / 7, fd / 3);
            ctx.font = `${fSize}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            const label = (item.name || '').length > 12
                ? (item.name || '').slice(0, 11) + '…'
                : item.name || '';
            ctx.fillText(label, 0, 0);
        }

        ctx.restore();
    },

    // ─── Individual Symbol Renderers ─────────────────────────────

    _drawDesk(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;

        // Desk surface
        ctx.beginPath();
        ctx.rect(-hw, -hd, w, d);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Front edge highlight (thicker line at front)
        ctx.beginPath();
        ctx.moveTo(-hw, hd);
        ctx.lineTo(hw, hd);
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Knee space indicator (slight indent on front)
        const kneeW = w * 0.5;
        ctx.beginPath();
        ctx.moveTo(-kneeW / 2, hd);
        ctx.lineTo(-kneeW / 2, hd - d * 0.15);
        ctx.lineTo(kneeW / 2, hd - d * 0.15);
        ctx.lineTo(kneeW / 2, hd);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 2]);
        ctx.stroke();
        ctx.setLineDash([]);
    },

    _drawChair(ctx, w, d, stroke, fill) {
        const r = Math.min(w, d) / 2;

        // Seat — circle
        ctx.beginPath();
        ctx.arc(0, 0, r * 0.8, 0, Math.PI * 2);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Backrest — arc at back
        ctx.beginPath();
        ctx.arc(0, 0, r, Math.PI * 0.7, Math.PI * 1.3);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Small indicator for front direction
        ctx.beginPath();
        ctx.moveTo(0, r * 0.4);
        ctx.lineTo(0, r * 0.7);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 0.8;
        ctx.stroke();
    },

    _drawMeetingTable(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;
        const r = Math.min(hw, hd) * 0.15;

        // Table surface — rounded rectangle
        ctx.beginPath();
        ctx.roundRect(-hw, -hd, w, d, r);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Inner line (table edge detail)
        const inset = 3;
        ctx.beginPath();
        ctx.roundRect(-hw + inset, -hd + inset, w - inset * 2, d - inset * 2, r);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 0.5;
        ctx.stroke();

        // Chair positions around table
        const chairR = Math.min(w, d) * 0.06;
        const positions = [];

        // Top and bottom edges
        const numH = Math.max(2, Math.floor(w / 60));
        for (let i = 0; i < numH; i++) {
            const x = -hw + (w / (numH + 1)) * (i + 1);
            positions.push({ x, y: -hd - chairR * 2.5 });
            positions.push({ x, y: hd + chairR * 2.5 });
        }
        // Left and right heads
        if (d > 80) {
            positions.push({ x: -hw - chairR * 2.5, y: 0 });
            positions.push({ x: hw + chairR * 2.5, y: 0 });
        }

        for (const pos of positions) {
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, chairR, 0, Math.PI * 2);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 0.8;
            ctx.stroke();
        }
    },

    _drawSharedTable(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;

        // Table surface
        ctx.beginPath();
        ctx.rect(-hw, -hd, w, d);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Center divider line
        ctx.beginPath();
        ctx.moveTo(-hw + 5, 0);
        ctx.lineTo(hw - 5, 0);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([4, 3]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Chair positions on both sides
        const chairR = Math.min(w, d) * 0.05;
        const numChairs = Math.max(2, Math.floor(w / 70));
        for (let i = 0; i < numChairs; i++) {
            const x = -hw + (w / (numChairs + 1)) * (i + 1);
            // Top side
            ctx.beginPath();
            ctx.arc(x, -hd - chairR * 2.5, chairR, 0, Math.PI * 2);
            ctx.stroke();
            // Bottom side
            ctx.beginPath();
            ctx.arc(x, hd + chairR * 2.5, chairR, 0, Math.PI * 2);
            ctx.stroke();
        }
    },

    _drawStorage(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;

        // Cabinet
        ctx.beginPath();
        ctx.rect(-hw, -hd, w, d);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Shelf lines
        const numShelves = Math.max(1, Math.floor(d / 20));
        for (let i = 1; i <= numShelves; i++) {
            const y = -hd + (d / (numShelves + 1)) * i;
            ctx.beginPath();
            ctx.moveTo(-hw + 2, y);
            ctx.lineTo(hw - 2, y);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 0.5;
            ctx.stroke();
        }

        // X marks on front (handle indicator)
        ctx.beginPath();
        ctx.moveTo(-hw * 0.3, hd - 3);
        ctx.lineTo(hw * 0.3, hd - 3);
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1;
        ctx.stroke();
    },

    _drawBench(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;

        // Bench seat
        ctx.beginPath();
        ctx.roundRect(-hw, -hd, w, d, 3);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Seat dividers
        const numSeats = Math.max(2, Math.floor(w / 60));
        for (let i = 1; i < numSeats; i++) {
            const x = -hw + (w / numSeats) * i;
            ctx.beginPath();
            ctx.moveTo(x, -hd + 2);
            ctx.lineTo(x, hd - 2);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 0.5;
            ctx.setLineDash([2, 2]);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Backrest line
        ctx.beginPath();
        ctx.moveTo(-hw, -hd);
        ctx.lineTo(hw, -hd);
        ctx.lineWidth = 3;
        ctx.strokeStyle = stroke;
        ctx.stroke();
    },

    _drawLounge(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;
        const armW = w * 0.12;
        const backD = d * 0.2;

        // Seat cushion
        ctx.beginPath();
        ctx.roundRect(-hw + armW, -hd + backD, w - armW * 2, d - backD, 4);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1;
        ctx.stroke();

        // Back
        ctx.beginPath();
        ctx.roundRect(-hw, -hd, w, backD, [4, 4, 0, 0]);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Left arm
        ctx.beginPath();
        ctx.roundRect(-hw, -hd, armW, d, [4, 0, 0, 4]);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Right arm
        ctx.beginPath();
        ctx.roundRect(hw - armW, -hd, armW, d, [0, 4, 4, 0]);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.5;
        ctx.stroke();
    },

    _drawGeneric(ctx, w, d, stroke, fill) {
        const hw = w / 2, hd = d / 2;
        ctx.beginPath();
        ctx.rect(-hw, -hd, w, d);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 1.2;
        ctx.stroke();
    },

    // ─── 3D Isometric Helpers ────────────────────────────────────

    /**
     * Build Three.js mesh for a furniture category (minimal but recognizable).
     */
    build3D(THREE, item) {
        const group = new THREE.Group();
        const color = new THREE.Color(item.color || '#888888');
        const w = item.width;
        const d = item.depth;

        switch (item.category) {
            case 'work_desk':
                this._build3DDesk(THREE, group, w, d, color);
                break;
            case 'chair':
                this._build3DChair(THREE, group, w, d, color);
                break;
            case 'meeting_table':
            case 'shared_table':
                this._build3DTable(THREE, group, w, d, color);
                break;
            case 'storage':
                this._build3DStorage(THREE, group, w, d, color);
                break;
            case 'lounge':
                this._build3DLounge(THREE, group, w, d, color);
                break;
            case 'collaborative_seating':
                this._build3DBench(THREE, group, w, d, color);
                break;
            default:
                this._build3DGeneric(THREE, group, w, d, color, 75);
        }

        group.position.set(item.x, 0, item.y);
        group.rotation.y = -(item.rotation || 0) * Math.PI / 180;

        return group;
    },

    _build3DDesk(THREE, group, w, d, color) {
        const topH = 4;
        const legH = 71;
        const legW = 4;

        // Table top
        const top = new THREE.Mesh(
            new THREE.BoxGeometry(w, topH, d),
            new THREE.MeshLambertMaterial({ color })
        );
        top.position.y = legH + topH / 2;
        top.castShadow = true;
        group.add(top);

        // 4 legs
        const legGeo = new THREE.BoxGeometry(legW, legH, legW);
        const legMat = new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.7) });
        const offsets = [
            [-w / 2 + legW, -d / 2 + legW],
            [w / 2 - legW, -d / 2 + legW],
            [-w / 2 + legW, d / 2 - legW],
            [w / 2 - legW, d / 2 - legW],
        ];
        for (const [ox, oz] of offsets) {
            const leg = new THREE.Mesh(legGeo, legMat);
            leg.position.set(ox, legH / 2, oz);
            group.add(leg);
        }
    },

    _build3DChair(THREE, group, w, d, color) {
        const seatH = 45;
        const seatThick = 4;
        const backH = 40;
        const backThick = 3;
        const legW = 3;
        const r = Math.min(w, d) / 2;

        // Seat (cylinder for round seat)
        const seat = new THREE.Mesh(
            new THREE.CylinderGeometry(r * 0.7, r * 0.7, seatThick, 16),
            new THREE.MeshLambertMaterial({ color })
        );
        seat.position.y = seatH;
        seat.castShadow = true;
        group.add(seat);

        // Backrest
        const back = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.7, backH, backThick),
            new THREE.MeshLambertMaterial({ color })
        );
        back.position.set(0, seatH + backH / 2, -d * 0.35);
        group.add(back);

        // Central pedestal
        const pedestal = new THREE.Mesh(
            new THREE.CylinderGeometry(3, 3, seatH - 5, 8),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.6) })
        );
        pedestal.position.y = (seatH - 5) / 2;
        group.add(pedestal);

        // Base (star shape approximated by cylinder)
        const base = new THREE.Mesh(
            new THREE.CylinderGeometry(r * 0.6, r * 0.6, 3, 5),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.5) })
        );
        base.position.y = 1.5;
        group.add(base);
    },

    _build3DTable(THREE, group, w, d, color) {
        const topH = 5;
        const legH = 70;
        const legW = 5;

        // Table top
        const top = new THREE.Mesh(
            new THREE.BoxGeometry(w, topH, d),
            new THREE.MeshLambertMaterial({ color })
        );
        top.position.y = legH + topH / 2;
        top.castShadow = true;
        group.add(top);

        // 4 legs
        const legGeo = new THREE.BoxGeometry(legW, legH, legW);
        const legMat = new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.7) });
        const margin = 8;
        const offsets = [
            [-w / 2 + margin, -d / 2 + margin],
            [w / 2 - margin, -d / 2 + margin],
            [-w / 2 + margin, d / 2 - margin],
            [w / 2 - margin, d / 2 - margin],
        ];
        for (const [ox, oz] of offsets) {
            const leg = new THREE.Mesh(legGeo, legMat);
            leg.position.set(ox, legH / 2, oz);
            group.add(leg);
        }
    },

    _build3DStorage(THREE, group, w, d, color) {
        const h = 180;

        // Main body
        const body = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshLambertMaterial({ color })
        );
        body.position.y = h / 2;
        body.castShadow = true;
        group.add(body);

        // Shelf lines (thin boxes)
        const numShelves = 4;
        const shelfMat = new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.8) });
        for (let i = 1; i <= numShelves; i++) {
            const shelf = new THREE.Mesh(
                new THREE.BoxGeometry(w - 4, 2, d - 4),
                shelfMat
            );
            shelf.position.y = (h / (numShelves + 1)) * i;
            group.add(shelf);
        }
    },

    _build3DLounge(THREE, group, w, d, color) {
        const seatH = 40;
        const armH = 55;
        const backH = 65;
        const armW = w * 0.12;

        // Seat
        const seat = new THREE.Mesh(
            new THREE.BoxGeometry(w - armW * 2, seatH * 0.4, d * 0.8),
            new THREE.MeshLambertMaterial({ color })
        );
        seat.position.set(0, seatH * 0.2, d * 0.1);
        seat.castShadow = true;
        group.add(seat);

        // Back
        const back = new THREE.Mesh(
            new THREE.BoxGeometry(w, backH, d * 0.2),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.9) })
        );
        back.position.set(0, backH / 2, -d * 0.4);
        group.add(back);

        // Left arm
        const larm = new THREE.Mesh(
            new THREE.BoxGeometry(armW, armH, d),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.85) })
        );
        larm.position.set(-w / 2 + armW / 2, armH / 2, 0);
        group.add(larm);

        // Right arm
        const rarm = new THREE.Mesh(
            new THREE.BoxGeometry(armW, armH, d),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.85) })
        );
        rarm.position.set(w / 2 - armW / 2, armH / 2, 0);
        group.add(rarm);
    },

    _build3DBench(THREE, group, w, d, color) {
        const seatH = 45;
        const seatThick = 5;
        const backH = 35;

        // Seat
        const seat = new THREE.Mesh(
            new THREE.BoxGeometry(w, seatThick, d),
            new THREE.MeshLambertMaterial({ color })
        );
        seat.position.y = seatH;
        seat.castShadow = true;
        group.add(seat);

        // Backrest
        const back = new THREE.Mesh(
            new THREE.BoxGeometry(w, backH, 3),
            new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.9) })
        );
        back.position.set(0, seatH + backH / 2, -d / 2);
        group.add(back);

        // Legs
        const legGeo = new THREE.BoxGeometry(4, seatH, 4);
        const legMat = new THREE.MeshLambertMaterial({ color: color.clone().multiplyScalar(0.6) });
        const numLegs = Math.max(2, Math.ceil(w / 60));
        for (let i = 0; i < numLegs; i++) {
            const x = -w / 2 + 10 + (w - 20) * (i / (numLegs - 1 || 1));
            const legF = new THREE.Mesh(legGeo, legMat);
            legF.position.set(x, seatH / 2, d / 2 - 4);
            group.add(legF);
            const legB = new THREE.Mesh(legGeo, legMat);
            legB.position.set(x, seatH / 2, -d / 2 + 4);
            group.add(legB);
        }
    },

    _build3DGeneric(THREE, group, w, d, color, h) {
        const mesh = new THREE.Mesh(
            new THREE.BoxGeometry(w, h, d),
            new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.85 })
        );
        mesh.position.y = h / 2;
        mesh.castShadow = true;
        group.add(mesh);
    },
};
