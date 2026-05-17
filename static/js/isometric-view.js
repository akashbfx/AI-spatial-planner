/**
 * 3D Isometric View — Three.js visualization with minimal but recognizable furniture.
 */

const IsometricView = {
    scene: null,
    camera: null,
    renderer: null,
    animationId: null,
    isMouseDown: false,
    mouseX: 0,
    mouseY: 0,
    rotY: Math.PI / 4,
    rotX: Math.PI / 6,

    render(layout, data) {
        this.dispose();

        const container = document.getElementById('three-container');
        const w = container.clientWidth || 700;
        const h = container.clientHeight || 500;

        // Scene
        this.scene = new THREE.Scene();
        const isDark = !document.body.classList.contains('light-theme');
        this.scene.background = new THREE.Color(isDark ? 0x0a0a1a : 0xf0f0f5);
        this.scene.fog = new THREE.FogExp2(isDark ? 0x0a0a1a : 0xf0f0f5, 0.0008);

        // Camera — orthographic for isometric
        const aspect = w / h;
        const frustumSize = 800;
        this.camera = new THREE.OrthographicCamera(
            -frustumSize * aspect / 2, frustumSize * aspect / 2,
            frustumSize / 2, -frustumSize / 2,
            0.1, 5000
        );

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(w, h);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        container.innerHTML = '';
        container.appendChild(this.renderer.domElement);

        // Build scene
        const roomData = data.room || RoomCanvas.getRoomData();
        this.buildRoom(roomData, isDark);
        this.buildFurniture(layout.placements);
        this.buildLighting(isDark);

        // Center camera
        const bounds = this.getRoomBounds(roomData.vertices);
        const cx = (bounds.minX + bounds.maxX) / 2;
        const cy = (bounds.minY + bounds.maxY) / 2;

        this.updateCamera(cx, cy);
        this.bindMouse(container);
        this.animate();
    },

    buildRoom(roomData, isDark) {
        const vertices = roomData.vertices;
        if (!vertices || vertices.length < 3) return;

        // Floor
        const shape = new THREE.Shape();
        shape.moveTo(vertices[0][0], vertices[0][1]);
        for (let i = 1; i < vertices.length; i++) {
            shape.lineTo(vertices[i][0], vertices[i][1]);
        }
        shape.closePath();

        const floorGeom = new THREE.ShapeGeometry(shape);
        const floorMat = new THREE.MeshLambertMaterial({
            color: isDark ? 0x1a1a35 : 0xe8e8f0,
            side: THREE.DoubleSide,
        });
        const floor = new THREE.Mesh(floorGeom, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Floor grid
        const bounds = this.getRoomBounds(vertices);
        const gridSize = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY);
        const gridHelper = new THREE.GridHelper(
            gridSize * 1.5,
            Math.floor(gridSize / 100),
            isDark ? 0x222244 : 0xccccdd,
            isDark ? 0x111133 : 0xddddee
        );
        gridHelper.position.set(
            (bounds.minX + bounds.maxX) / 2, 0,
            (bounds.minY + bounds.maxY) / 2
        );
        this.scene.add(gridHelper);

        // Walls (extruded)
        const wallHeight = 280;
        for (let i = 0; i < vertices.length; i++) {
            const a = vertices[i];
            const b = vertices[(i + 1) % vertices.length];

            const wallLen = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);

            const wallGeom = new THREE.BoxGeometry(wallLen, wallHeight, 8);
            const wallMat = new THREE.MeshLambertMaterial({
                color: isDark ? 0x2a2a50 : 0xbbbbcc,
                transparent: true,
                opacity: 0.35,
            });
            const wall = new THREE.Mesh(wallGeom, wallMat);
            wall.position.set(
                (a[0] + b[0]) / 2, wallHeight / 2,
                (a[1] + b[1]) / 2
            );
            wall.rotation.y = -angle;
            this.scene.add(wall);
        }

        // Windows
        for (const win of (roomData.windows || [])) {
            const winGeom = new THREE.BoxGeometry(win.width, win.head_height - win.sill_height, 12);
            const winMat = new THREE.MeshLambertMaterial({
                color: 0xffd54f,
                transparent: true,
                opacity: 0.4,
                emissive: 0xffd54f,
                emissiveIntensity: 0.2,
            });
            const winMesh = new THREE.Mesh(winGeom, winMat);
            winMesh.position.set(
                win.position[0],
                win.sill_height + (win.head_height - win.sill_height) / 2,
                win.position[1]
            );
            this.scene.add(winMesh);
        }

        // Doors
        for (const door of (roomData.doors || [])) {
            const doorGeom = new THREE.BoxGeometry(door.width, 210, 10);
            const doorMat = new THREE.MeshLambertMaterial({
                color: 0x4fc3f7,
                transparent: true,
                opacity: 0.35,
            });
            const doorMesh = new THREE.Mesh(doorGeom, doorMat);
            doorMesh.position.set(door.position[0], 105, door.position[1]);
            this.scene.add(doorMesh);
        }
    },

    buildFurniture(placements) {
        for (const item of placements) {
            const group = FurnitureSymbols.build3D(THREE, item);
            this.scene.add(group);
        }
    },

    buildLighting(isDark) {
        const ambient = new THREE.AmbientLight(
            isDark ? 0x404060 : 0x808090,
            isDark ? 0.6 : 0.8
        );
        this.scene.add(ambient);

        const sun = new THREE.DirectionalLight(isDark ? 0xffeedd : 0xffffff, isDark ? 0.8 : 0.6);
        sun.position.set(500, 800, -300);
        sun.castShadow = true;
        this.scene.add(sun);

        const point1 = new THREE.PointLight(0x4A90D9, 0.3, 1000);
        point1.position.set(300, 400, 300);
        this.scene.add(point1);
    },

    getRoomBounds(vertices) {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const v of (vertices || [[0, 0]])) {
            minX = Math.min(minX, v[0]); minY = Math.min(minY, v[1]);
            maxX = Math.max(maxX, v[0]); maxY = Math.max(maxY, v[1]);
        }
        return { minX, minY, maxX, maxY };
    },

    updateCamera(cx, cy) {
        const dist = 800;
        this.camera.position.set(
            cx + dist * Math.sin(this.rotY) * Math.cos(this.rotX),
            dist * Math.sin(this.rotX) + 200,
            cy + dist * Math.cos(this.rotY) * Math.cos(this.rotX)
        );
        this.camera.lookAt(cx, 50, cy);
        this.camera.updateProjectionMatrix();
    },

    bindMouse(container) {
        const el = this.renderer.domElement;
        const roomData = RoomCanvas.getRoomData();
        const bounds = this.getRoomBounds(roomData.vertices || [[0, 0]]);
        const cx = (bounds.minX + bounds.maxX) / 2;
        const cy = (bounds.minY + bounds.maxY) / 2;

        el.addEventListener('mousedown', (e) => {
            this.isMouseDown = true;
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });

        el.addEventListener('mousemove', (e) => {
            if (!this.isMouseDown) return;
            const dx = e.clientX - this.mouseX;
            const dy = e.clientY - this.mouseY;
            this.rotY += dx * 0.005;
            this.rotX = Math.max(0.1, Math.min(Math.PI / 2.5, this.rotX + dy * 0.005));
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
            this.updateCamera(cx, cy);
        });

        el.addEventListener('mouseup', () => { this.isMouseDown = false; });
        el.addEventListener('mouseleave', () => { this.isMouseDown = false; });

        el.addEventListener('wheel', (e) => {
            const zoom = e.deltaY > 0 ? 1.05 : 0.95;
            this.camera.zoom *= zoom;
            this.camera.zoom = Math.max(0.3, Math.min(3, this.camera.zoom));
            this.camera.updateProjectionMatrix();
            e.preventDefault();
        }, { passive: false });
    },

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    },

    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        if (this.renderer) {
            this.renderer.dispose();
            this.renderer = null;
        }
        this.scene = null;
        this.camera = null;
        this.rotY = Math.PI / 4;
        this.rotX = Math.PI / 6;
    },
};
