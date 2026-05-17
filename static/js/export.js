/**
 * Export module — SVG and PNG export of layouts.
 */

const Export = {
    init() {
        document.getElementById('btn-export-svg').addEventListener('click', () => this.exportSVG());
        document.getElementById('btn-export-png').addEventListener('click', () => this.exportPNG());
    },

    async exportSVG() {
        const layout = LayoutViewer.currentLayout || (LayoutViewer.layouts.length > 0 ? LayoutViewer.layouts[0] : null);
        if (!layout) {
            Utils.toast('Generate layouts first', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/export-svg', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    layout: layout,
                    room: RoomCanvas.getRoomData(),
                }),
            });

            if (!response.ok) throw new Error('Export failed');

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `spaceai_layout_${layout.layout_id}.svg`;
            a.click();
            URL.revokeObjectURL(url);

            Utils.toast('SVG exported!', 'success');
        } catch (err) {
            Utils.toast('SVG export failed: ' + err.message, 'error');
        }
    },

    exportPNG() {
        // Use the detail canvas if modal is open, otherwise use the first layout card
        let canvas = document.getElementById('detail-canvas');
        if (document.getElementById('layout-modal').classList.contains('hidden')) {
            // Find first layout card canvas
            const cardCanvas = document.querySelector('.layout-card-canvas canvas');
            if (cardCanvas) canvas = cardCanvas;
        }

        if (!canvas) {
            Utils.toast('No layout to export', 'warning');
            return;
        }

        try {
            const dataURL = canvas.toDataURL('image/png');
            const a = document.createElement('a');
            a.href = dataURL;
            a.download = `spaceai_layout.png`;
            a.click();
            Utils.toast('PNG exported!', 'success');
        } catch (err) {
            Utils.toast('PNG export failed: ' + err.message, 'error');
        }
    },
};
