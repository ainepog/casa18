let currentCuotaId = null;

// ==========================================
// 1. CONTROL DE APERTURA Y CIERRE DE MODALES
// ==========================================
function abrirModalUpload(id) {
    currentCuotaId = id;
    document.getElementById('modalUpload').style.display = 'flex';
    document.getElementById('uploadStatus').innerText = '';
}

function abrirModalPreview(url) {
    const previewFrame = document.getElementById('previewFrame');

    const fullUrl = window.location.origin + url;

    previewFrame.src = `https://docs.google.com/viewer?url=${encodeURIComponent(fullUrl)}&embedded=true`;

    document.getElementById('modalPreview').style.display = 'flex';
}

function cerrarModal(id) {
    document.getElementById(id).style.display = 'none';
    if(id === 'modalPreview') {
        document.getElementById('previewFrame').src = '';
    }
}

// ==========================================
// 2. LÓGICA DE ARRASTRAR Y SOLTAR (DRAG & DROP)
// ==========================================
document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');

    if (dropzone && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
        });

        dropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length) uploadFile(files[0]);
        });

        fileInput.addEventListener('change', function() {
            if (this.files.length) uploadFile(this.files[0]);
        });
    }
});

// ==========================================
// 3. ENVÍO AL SERVIDOR (AJAX)
// ==========================================
function uploadFile(file) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.style.color = '#17a2b8';
    statusDiv.innerText = 'Subiendo archivo... ';

    const formData = new FormData();
    formData.append('comprobante', file);

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    const basePath = window.location.pathname.split('?')[0];

    fetch(`${basePath}${currentCuotaId}/upload-ajax/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'ok') {
            statusDiv.style.color = '#28a745';
            statusDiv.innerText = 'Constancia guardada';
            setTimeout(() => location.reload(), 800);
        } else {
            throw new Error('El servidor devolvió un error.');
        }
    })
    .catch(error => {
        statusDiv.style.color = '#dc3545';
        statusDiv.innerText = 'Error al subir el archivo, revise el formato.';
        console.error(error);
    });
}