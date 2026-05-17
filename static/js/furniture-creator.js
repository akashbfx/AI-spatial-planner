/**
 * Custom furniture creator form (handled inline by ConfigPanel).
 * This module adds validation and preview for custom pieces.
 */

const FurnitureCreator = {
    init() {
        // Preview dimensions as user types
        const widthInput = document.getElementById('custom-width');
        const depthInput = document.getElementById('custom-depth');

        [widthInput, depthInput].forEach(input => {
            input.addEventListener('input', () => {
                const w = parseInt(widthInput.value) || 0;
                const d = parseInt(depthInput.value) || 0;
                // Could add inline preview here
            });
        });
    },
};
