document.addEventListener('DOMContentLoaded', () => {
    const geomField = document.getElementById('id_geometry');

    if (geomField) {
        geomField.removeAttribute('hidden');
        geomField.style.display = 'block';
        geomField.style.width = '100%';
    }
});