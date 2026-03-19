// Variables
const canvas = document.getElementById('signaturePad');
const ctx = canvas.getContext('2d');
const clearBtn = document.getElementById('clearBtn');
const saveBtn = document.getElementById('saveBtn');
const employeeIdInput = document.getElementById('employeeId');
const employeeNameInput = document.getElementById('employeeName');
const canvasContainer = document.getElementById('canvasContainer');
const captureSection = document.getElementById('captureSection');
const warningMessage = document.getElementById('warningMessage');

// State
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// Setup canvas size properly for high DPI displays and responsive
function resizeCanvas() {
    const rect = canvasContainer.getBoundingClientRect();

    // Save current content before resize
    const dataUrl = canvas.toDataURL();

    // Set actual size in memory (scaled to account for extra pixel density).
    // A scale of 1 is enough for the functionality, let's keep it simple for now to avoid coordinate mismatches.
    canvas.width = rect.width;
    canvas.height = rect.height;

    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;

    // Drawing settings
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'black';
    ctx.fillStyle = 'black'; // for dots

    // Restore content if exists
    if (dataUrl.length > 30) {
        const img = new Image();
        img.onload = () => {
            ctx.drawImage(img, 0, 0, rect.width, rect.height);
        };
        img.src = dataUrl;
    }
}

// Inputs check
function checkInputs() {
    const isIdFilled = employeeIdInput.value.trim() !== '';
    const isNameFilled = employeeNameInput.value.trim() !== '';

    if (isIdFilled && isNameFilled) {
        captureSection.classList.remove('opacity-50', 'pointer-events-none');
        warningMessage.classList.add('hidden');
    } else {
        captureSection.classList.add('opacity-50', 'pointer-events-none');
        warningMessage.classList.remove('hidden');
    }
}

employeeIdInput.addEventListener('input', checkInputs);
employeeNameInput.addEventListener('input', checkInputs);

// Initial resize and check
window.addEventListener('load', () => {
    resizeCanvas();
    checkInputs();
});
window.addEventListener('resize', resizeCanvas);

// Drawing logic
function getCoordinates(e) {
    const rect = canvas.getBoundingClientRect();
    // Use scaling to handle canvas width/height ratio correctly
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    if (e.touches && e.touches.length > 0) {
        return {
            x: (e.touches[0].clientX - rect.left) * scaleX,
            y: (e.touches[0].clientY - rect.top) * scaleY
        };
    } else {
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }
}

function startDrawing(e) {
    isDrawing = true;
    const coords = getCoordinates(e);
    lastX = coords.x;
    lastY = coords.y;

    // Draw a single dot if it's just a tap
    ctx.beginPath();
    ctx.arc(lastX, lastY, ctx.lineWidth / 2, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
}

function draw(e) {
    if (!isDrawing) return;
    e.preventDefault(); // Prevent scrolling on touch devices

    const coords = getCoordinates(e);

    ctx.lineTo(coords.x, coords.y);
    ctx.stroke();

    // Smooth curves for drawing
    ctx.beginPath();
    ctx.moveTo(coords.x, coords.y);

    lastX = coords.x;
    lastY = coords.y;
}

function stopDrawing() {
    isDrawing = false;
    ctx.beginPath(); // start a new path to prevent connecting lines later
}

// Event Listeners for drawing
canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

canvas.addEventListener('touchstart', startDrawing, {passive: false});
canvas.addEventListener('touchmove', draw, {passive: false});
canvas.addEventListener('touchend', stopDrawing);

// Clear Canvas
clearBtn.addEventListener('click', () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
});

// Image Upload and Processing logic
const imageUpload = document.getElementById('imageUpload');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const previewCanvas = document.getElementById('previewCanvas');
const previewCtx = previewCanvas.getContext('2d');
const thresholdSlider = document.getElementById('thresholdSlider');
const extractBtn = document.getElementById('extractBtn');

let uploadedImage = null;

imageUpload.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(event) {
        uploadedImage = new Image();
        uploadedImage.onload = function() {
            // Show preview container
            imagePreviewContainer.classList.remove('hidden');
            previewCanvas.classList.remove('hidden');

            // Resize preview canvas
            const maxWidth = imagePreviewContainer.clientWidth - 32; // padding
            const scale = Math.min(1, maxWidth / uploadedImage.width);

            previewCanvas.width = uploadedImage.width * scale;
            previewCanvas.height = uploadedImage.height * scale;

            processImage();
        };
        uploadedImage.src = event.target.result;
    };
    reader.readAsDataURL(file);
});

thresholdSlider.addEventListener('input', () => {
    if (uploadedImage) processImage();
});

function processImage() {
    if (!uploadedImage) return;

    // Draw original scaled image
    previewCtx.drawImage(uploadedImage, 0, 0, previewCanvas.width, previewCanvas.height);

    // Get image data
    const imageData = previewCtx.getImageData(0, 0, previewCanvas.width, previewCanvas.height);
    const data = imageData.data;
    const threshold = parseInt(thresholdSlider.value);

    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // Convert to grayscale
        const gray = 0.299 * r + 0.587 * g + 0.114 * b;

        // Apply threshold and transparency
        if (gray > threshold) {
            // White background becomes transparent
            data[i + 3] = 0; // Alpha
        } else {
            // Make drawing black
            data[i] = 0;
            data[i + 1] = 0;
            data[i + 2] = 0;
            data[i + 3] = 255;
        }
    }

    previewCtx.putImageData(imageData, 0, 0);
}

extractBtn.addEventListener('click', () => {
    if (!uploadedImage) return;

    // Clear main canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calculate dimensions to fit the main canvas while preserving aspect ratio
    const scale = Math.min(canvas.width / previewCanvas.width, canvas.height / previewCanvas.height);
    const w = previewCanvas.width * scale;
    const h = previewCanvas.height * scale;
    const x = (canvas.width - w) / 2;
    const y = (canvas.height - h) / 2;

    // Draw the processed image to the main canvas
    ctx.drawImage(previewCanvas, x, y, w, h);

    // Hide preview
    imagePreviewContainer.classList.add('hidden');
    imageUpload.value = ''; // Reset input
    uploadedImage = null;
});


// Save logic
saveBtn.addEventListener('click', () => {
    const employeeId = employeeIdInput.value.trim();
    const employeeName = employeeNameInput.value.trim();

    if (!employeeId || !employeeName) {
        alert('Por favor, informe a matrícula e o nome do funcionário.');
        return;
    }

    const dataURL = canvas.toDataURL('image/png');

    saveBtn.disabled = true;
    saveBtn.innerText = 'Enviando...';
    saveBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
    saveBtn.classList.add('bg-gray-400');

    fetch('/upload', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            matricula: employeeId,
            nome: employeeName,
            image: dataURL
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert('Assinatura salva com sucesso!');
            // Reset state
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            employeeIdInput.value = '';
            employeeNameInput.value = '';
            checkInputs();
        } else {
            alert('Erro ao salvar: ' + (data.message || 'Desconhecido'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Erro de conexão ao salvar a assinatura.');
    })
    .finally(() => {
        saveBtn.disabled = false;
        saveBtn.innerText = 'Salvar e Enviar';
        saveBtn.classList.remove('bg-gray-400');
        saveBtn.classList.add('bg-green-600', 'hover:bg-green-700');
    });
});
