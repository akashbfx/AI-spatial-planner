/**
 * Utility functions for SpaceAI
 */

const Utils = {
    /**
     * Fetch JSON from API endpoint
     */
    async fetchJSON(url, options = {}) {
        try {
            const resp = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                ...options,
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } catch (err) {
            console.error(`API Error (${url}):`, err);
            throw err;
        }
    },

    async postJSON(url, data) {
        return this.fetchJSON(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    /**
     * Convert meters to cm
     */
    mToCm(m) { return m * 100; },
    cmToM(cm) { return cm / 100; },

    /**
     * Snap value to grid
     */
    snap(val, grid = 10) {
        return Math.round(val / grid) * grid;
    },

    /**
     * Get compass direction label
     */
    compassLabel(degrees) {
        const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
        const idx = Math.round(degrees / 45) % 8;
        return dirs[idx];
    },

    /**
     * Format area for display
     */
    formatArea(sqcm) {
        return (sqcm / 10000).toFixed(1);
    },

    /**
     * Lighten a hex color
     */
    lightenColor(hex, amount = 0.3) {
        hex = hex.replace('#', '');
        const r = Math.min(255, parseInt(hex.substr(0, 2), 16) + Math.floor(255 * amount));
        const g = Math.min(255, parseInt(hex.substr(2, 2), 16) + Math.floor(255 * amount));
        const b = Math.min(255, parseInt(hex.substr(4, 2), 16) + Math.floor(255 * amount));
        return `rgb(${r},${g},${b})`;
    },

    /**
     * Generate unique ID
     */
    uid() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    },

    /**
     * Debounce function
     */
    debounce(fn, delay = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },

    /**
     * Show a toast notification
     */
    toast(message, type = 'info', duration = 3000) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = 'position:fixed;top:70px;right:20px;z-index:400;display:flex;flex-direction:column;gap:8px;';
            document.body.appendChild(container);
        }

        const colors = {
            info: '#4A90D9',
            success: '#50B86C',
            warning: '#E8833A',
            error: '#E74C3C'
        };

        const toast = document.createElement('div');
        toast.style.cssText = `
            padding: 10px 16px;
            background: rgba(17, 17, 40, 0.95);
            border: 1px solid ${colors[type]};
            border-left: 3px solid ${colors[type]};
            color: #e8e8f0;
            font-size: 0.82rem;
            border-radius: 8px;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            animation: toastIn 0.3s ease;
            max-width: 320px;
        `;
        toast.textContent = message;
        container.appendChild(toast);

        // Add toast animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes toastIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }
            @keyframes toastOut { from { opacity: 1; } to { opacity: 0; transform: translateX(30px); } }
        `;
        if (!document.getElementById('toast-styles')) {
            style.id = 'toast-styles';
            document.head.appendChild(style);
        }

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
};
