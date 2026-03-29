/* Dry station builder — shared JS for Dry_template_form and Dry_form_simple */
// Question type handlers
function updateQuestionType(select) {
    const card = select.closest('.checklist-item-card');
    const mcqEditor = card.querySelector('.mcq-editor');
    const essayEditor = card.querySelector('.essay-editor');
    if (select.value === 'mcq') {
        mcqEditor.style.display = '';
        essayEditor.classList.remove('visible');
    } else {
        mcqEditor.style.display = 'none';
        essayEditor.classList.add('visible');
    }
}

function selectCorrect(row) {
    const card = row.closest('.checklist-item-card');
    card.querySelectorAll('.mcq-option-row').forEach(r => {
        r.classList.remove('correct');
        r.querySelector('.mcq-correct-radio').checked = false;
        r.querySelector('.option-correct-indicator i').className = 'bi bi-circle';
    });
    row.classList.add('correct');
    row.querySelector('.mcq-correct-radio').checked = true;
    row.querySelector('.option-correct-indicator i').className = 'bi bi-check-circle-fill';
}

function fixMcqRadioNames(card) {
    const id = card.dataset.itemId;
    card.querySelectorAll('.mcq-correct-radio').forEach((radio, i) => {
        radio.name = `mcq_correct_${id}`;
        radio.value = i;
        // Sync .correct class and icon with checked state
        const row = radio.closest('.mcq-option-row');
        if (radio.checked) {
            row.classList.add('correct');
            row.querySelector('.option-correct-indicator i').className = 'bi bi-check-circle-fill';
        } else {
            row.classList.remove('correct');
            row.querySelector('.option-correct-indicator i').className = 'bi bi-circle';
        }
    });
    updateOptionLetters(card);
}

function updateOptionLetters(card) {
    card.querySelectorAll('.mcq-option-row').forEach((row, i) => {
        row.querySelector('.option-letter').textContent = String.fromCharCode(65 + i) + '.';
    });
}

function addMcqOption(btn) {
    const card = btn.closest('.checklist-item-card');
    const list = card.querySelector('.mcq-options-list');
    const count = list.querySelectorAll('.mcq-option-row').length;
    if (count >= 6) return;
    const letter = String.fromCharCode(65 + count);
    const id = card.dataset.itemId;
    const row = document.createElement('div');
    row.className = 'mcq-option-row';
    row.innerHTML = `
        <input type="radio" class="mcq-correct-radio" style="display:none" name="mcq_correct_${id}" value="${count}">
        <span class="option-correct-indicator" onclick="selectCorrect(this.closest('.mcq-option-row'))" title="Click to mark as correct"><i class="bi bi-circle"></i></span>
        <span class="option-letter">${letter}.</span>
        <input type="text" class="form-control form-control-sm mcq-option-input" placeholder="Option ${letter}...">
        <span class="correct-badge">✓ Correct</span>
        <button type="button" class="remove-option-btn" onclick="removeMcqOption(this)" title="Remove option"><i class="bi bi-x-lg"></i></button>
    `;
    list.appendChild(row);
}

function removeMcqOption(btn) {
    const card = btn.closest('.checklist-item-card');
    const list = card.querySelector('.mcq-options-list');
    if (list.querySelectorAll('.mcq-option-row').length <= 2) return;
    btn.closest('.mcq-option-row').remove();
    fixMcqRadioNames(card);
}

function getMcqData(card) {
    const options = [];
    let correctIndex = -1;
    card.querySelectorAll('.mcq-option-row').forEach((row, i) => {
        options.push(row.querySelector('.mcq-option-input').value.trim());
        if (row.querySelector('.mcq-correct-radio').checked) correctIndex = i;
    });
    return { options, correct_index: correctIndex };
}

function getKeyAnswer(card) {
    const ta = card.querySelector('.essay-key-answer');
    return ta ? ta.value.trim() : '';
}

let itemCounter = 0;
let sectionCounter = 0;

function addSection(title = '') {
    const container = document.getElementById('checklistContainer');
    const template = document.getElementById('sectionTemplate');
    const clone = template.content.cloneNode(true);
    
    sectionCounter++;
    const sectionCard = clone.querySelector('.section-header-card');
    sectionCard.dataset.sectionId = sectionCounter;
    
    const titleInput = clone.querySelector('.section-title-input');
    titleInput.value = title;
    
    container.appendChild(clone);
    
    const addedSection = container.lastElementChild;
    setupDragDrop(addedSection);
    
    if (!title) {
        addedSection.querySelector('.section-title-input').focus();
    }
}

function deleteSection(btn) {
    const card = btn.closest('.section-header-card');
    card.style.transform = 'translateX(100%)';
    card.style.opacity = '0';
    setTimeout(() => { card.remove(); }, 200);
}

function addNewItem(description = '', points = null, qtype = 'mcq', iloId = '', mcqOptions = null, correctIndex = -1, keyAnswer = '', imageUrl = null, dbId = null, startCollapsed = false, imagePath = null) {
    const container = document.getElementById('checklistContainer');
    const template = document.getElementById('itemTemplate');
    const clone = template.content.cloneNode(true);
    
    itemCounter++;
    const itemCard = clone.querySelector('.checklist-item-card');
    itemCard.dataset.itemId = itemCounter;
    if (dbId) itemCard.dataset.dbId = String(dbId);
    // Assign a unique name to this item's file input
    const imgFileInput = clone.querySelector('.img-file-input');
    if (imgFileInput) imgFileInput.name = 'item_image_' + itemCounter;
    
    const descInput = clone.querySelector('.item-description-input');
    descInput.value = description;
    
    const pointsChips = clone.querySelectorAll('.points-chip');
    let pointsSet = false;
    pointsChips.forEach(chip => {
        chip.classList.remove('active');
        if (points !== null && parseFloat(chip.dataset.pts) === points) {
            chip.classList.add('active');
            pointsSet = true;
        }
    });
    if (!pointsSet && points !== null && points !== undefined) {
        clone.querySelector('.points-custom-input').value = points;
    }
    
    clone.querySelector('.question-type-select').value = qtype;
    clone.querySelector('.ilo-select').value = iloId || '';
    
    container.appendChild(clone);
    
    const addedCard = container.lastElementChild;
    if (startCollapsed) {
        addedCard.classList.add('collapsed');
    }
    
    // Set radio button group names
    fixMcqRadioNames(addedCard);
    
    // Apply question type visibility
    const typeSelect = addedCard.querySelector('.question-type-select');
    updateQuestionType(typeSelect);
    
    // Restore MCQ options if provided
    if (qtype === 'mcq' && mcqOptions && mcqOptions.length > 0) {
        const list = addedCard.querySelector('.mcq-options-list');
        list.innerHTML = '';
        mcqOptions.forEach((opt, i) => {
            const letter = String.fromCharCode(65 + i);
            const isCorrect = i === correctIndex;
            const row = document.createElement('div');
            row.className = 'mcq-option-row' + (isCorrect ? ' correct' : '');
            row.innerHTML = `
                <input type="radio" class="mcq-correct-radio" style="display:none"
                       name="mcq_correct_${itemCounter}" value="${i}"
                       ${isCorrect ? 'checked' : ''}>
                <span class="option-correct-indicator" onclick="selectCorrect(this.closest('.mcq-option-row'))" title="Click to mark as correct"><i class="bi bi-${isCorrect ? 'check-circle-fill' : 'circle'}"></i></span>
                <span class="option-letter">${letter}.</span>
                <input type="text" class="form-control form-control-sm mcq-option-input" placeholder="Option ${letter}..." value="${opt.replace(/"/g, '&quot;')}">
                <span class="correct-badge">✓ Correct</span>
                <button type="button" class="remove-option-btn" onclick="removeMcqOption(this)" title="Remove option"><i class="bi bi-x-lg"></i></button>
            `;
            list.appendChild(row);
        });
    } else if (qtype === 'mcq') {
        // Default 4 options — fix radio names
        fixMcqRadioNames(addedCard);
    }
    
    // Restore essay key answer if provided
    if (qtype === 'essay' && keyAnswer) {
        addedCard.querySelector('.essay-key-answer').value = keyAnswer;
    }
    
    setupDragDrop(addedCard);
    
    // Restore existing image preview when editing a station
    if (imageUrl) {
        showImagePreview(addedCard, imageUrl, 'Existing image', null, null);
    }
    if (imagePath) {
        addedCard.dataset.imagePath = imagePath;
    }
    
    if (!description) {
        addedCard.querySelector('.item-description-input').focus();
    }
    
    renumberItems();
    updateSummary();
}

function deleteItem(btn) {
    const card = btn.closest('.checklist-item-card');
    card.style.transform = 'translateX(100%)';
    card.style.opacity = '0';
    setTimeout(() => {
        card.remove();
        renumberItems();
        updateSummary();
    }, 200);
}

function toggleItemFold(btn) {
    btn.closest('.checklist-item-card').classList.toggle('collapsed');
}

function duplicateItem(btn) {
    const card = btn.closest('.checklist-item-card');
    
    const description = card.querySelector('.item-description-input').value;
    const points = getItemPoints(card);
    const qtype = card.querySelector('.question-type-select').value;
    const iloId = card.querySelector('.ilo-select').value;
    const mcqData = qtype === 'mcq' ? getMcqData(card) : null;
    const keyAnswer = qtype === 'essay' ? getKeyAnswer(card) : '';
    
    const container = document.getElementById('checklistContainer');
    const cards = Array.from(container.querySelectorAll('.checklist-item-card'));
    const currentIndex = cards.indexOf(card);
    
    addNewItem(
        description, points, qtype, iloId,
        mcqData ? mcqData.options : null,
        mcqData ? mcqData.correct_index : -1,
        keyAnswer
    );
    
    const newCard = container.lastElementChild;
    const nextCard = cards[currentIndex + 1];
    if (nextCard) {
        container.insertBefore(newCard, nextCard);
    }
    
    newCard.style.backgroundColor = '#d1e7dd';
    setTimeout(() => { newCard.style.backgroundColor = ''; }, 500);
    
    newCard.querySelector('.item-description-input').focus();
    newCard.querySelector('.item-description-input').select();
    
    renumberItems();
}

function quickAddItems() {
    const textarea = document.getElementById('quickAddText');
    const lines = textarea.value.split('\n').filter(line => line.trim());
    
    lines.forEach(line => {
        addNewItem(line.trim(), null, 'mcq', '');
    });
    
    textarea.value = '';
}

function setPoints(chip, value) {
    const card = chip.closest('.checklist-item-card');
    card.querySelectorAll('.points-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    card.querySelector('.points-custom-input').value = '';
    updateSummary();
}

function setCustomPoints(input) {
    const card = input.closest('.checklist-item-card');
    card.querySelectorAll('.points-chip').forEach(c => c.classList.remove('active'));
    updateSummary();
}

function getItemPoints(card) {
    const activeChip = card.querySelector('.points-chip.active');
    if (activeChip) {
        return parseFloat(activeChip.dataset.pts);
    }
    const customInput = card.querySelector('.points-custom-input');
    const customVal = parseFloat(customInput.value);
    return isNaN(customVal) ? null : customVal;
}

function renumberItems() {
    let itemNum = 0;
    document.querySelectorAll('#checklistContainer > div').forEach((card) => {
        if (card.dataset.type === 'item') {
            itemNum++;
            card.querySelector('.item-number-badge').textContent = itemNum;
        }
    });
}

function updateSummary() {
    const items = document.querySelectorAll('.checklist-item-card');
    let totalPoints = 0;
    items.forEach(item => { totalPoints += getItemPoints(item); });
    document.getElementById('totalItems').textContent = items.length;
    document.getElementById('totalPoints').textContent = totalPoints % 1 === 0 ? totalPoints : totalPoints.toFixed(2);
    document.getElementById('itemCountBadge').textContent = `${items.length} items`;
}

// ── Image Upload ──────────────────────────────────────────────────────────────

function triggerImageUpload(zone) {
    if (zone.classList.contains('has-image')) return; // Use Replace button instead
    const card = zone.closest('.checklist-item-card');
    if (!card) return;
    card.querySelector('.img-file-input').click();
}

function handleImageChange(fileInput) {
    const card = fileInput.closest('.checklist-item-card');
    const errorEl = card.querySelector('.img-upload-error');
    const file = fileInput.files[0];

    errorEl.style.display = 'none';
    if (!file) return;

    // Client-side validation mirrors backend
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        errorEl.textContent = 'Only JPEG, PNG, or WebP files are allowed.';
        errorEl.style.display = 'block';
        fileInput.value = '';
        return;
    }
    if (file.size > 2 * 1024 * 1024) {
        errorEl.textContent = `File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 2 MB.`;
        errorEl.style.display = 'block';
        fileInput.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        const img = new Image();
        img.onload = function() {
            if (img.width < 100 || img.height < 100) {
                errorEl.textContent = `Image too small (${img.width}×${img.height}px). Minimum 100×100px.`;
                errorEl.style.display = 'block';
                fileInput.value = '';
                return;
            }
            if (img.width > 4000 || img.height > 4000) {
                errorEl.textContent = `Image too large (${img.width}×${img.height}px). Maximum 4000×4000px.`;
                errorEl.style.display = 'block';
                fileInput.value = '';
                return;
            }
            showImagePreview(card, e.target.result, file.name, img.width, img.height);
            // Clear any "image removed" flag
            delete card.dataset.imageRemoved;
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

function showImagePreview(card, src, name, w, h) {
    // Extract filename from URL for existing images (no dimensions provided)
    if (!w && !h) {
        try {
            const urlPath = src.split('?')[0];
            const extracted = decodeURIComponent(urlPath.split('/').pop());
            if (extracted) name = extracted;
        } catch(e) {}
    }
    const zone = card.querySelector('.img-upload-zone');
    const thumb = zone.querySelector('.img-preview-thumb');
    thumb.onerror = function() {
        // Image failed to load — reset preview to upload state
        zone.classList.remove('has-image');
        zone.style.cursor = '';
        thumb.src = '';
    };
    thumb.src = src;
    zone.querySelector('.img-preview-name').textContent = name;
    zone.querySelector('.img-preview-dims').textContent = (w && h) ? `${w} × ${h} px` : '';
    zone.classList.add('has-image');
    zone.style.cursor = 'default';
}

function handleImageDrop(zone, e) {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (zone.classList.contains('has-image')) return;
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const card = zone.closest('.checklist-item-card');
    if (!card) return;
    try {
        const dt = new DataTransfer();
        dt.items.add(file);
        const fileInput = card.querySelector('.img-file-input');
        fileInput.files = dt.files;
        handleImageChange(fileInput);
    } catch(err) {
        // DataTransfer not supported (older browsers) — ignore silently
    }
}

function replaceImage(btn) {
    const card = btn.closest('.checklist-item-card');
    const zone = card.querySelector('.img-upload-zone');
    zone.classList.remove('has-image');
    zone.style.cursor = '';
    card.querySelector('.img-file-input').click();
}

function removeImage(btn) {
    const card = btn.closest('.checklist-item-card');
    const zone = card.querySelector('.img-upload-zone');
    zone.querySelector('.img-preview-thumb').src = '';
    zone.querySelector('.img-preview-name').textContent = '';
    zone.querySelector('.img-preview-dims').textContent = '';
    zone.classList.remove('has-image');
    card.querySelector('.img-file-input').value = '';
    card.dataset.imageRemoved = 'true';
    delete card.dataset.imagePath; // Clear stored image path
}

// ── Drag and Drop ─────────────────────────────────────────────────────────────
function setupDragDrop(element) {
    element.draggable = true;
    element.dataset.dragReady = '0';

    const dragHandle = element.querySelector('.item-drag-handle');
    if (dragHandle) {
        dragHandle.addEventListener('pointerdown', () => {
            element.dataset.dragReady = '1';
        });
    }

    element.addEventListener('pointerup', () => {
        element.dataset.dragReady = '0';
    });
    element.addEventListener('pointercancel', () => {
        element.dataset.dragReady = '0';
    });

    element.addEventListener('dragstart', handleDragStart);
    element.addEventListener('dragend', handleDragEnd);
    element.addEventListener('dragover', handleDragOver);
    element.addEventListener('drop', handleDrop);
}

let draggedItem = null;

function handleDragStart(e) {
    if (this.dataset.dragReady !== '1') {
        e.preventDefault();
        e.dataTransfer.effectAllowed = 'none';
        return false;
    }

    draggedItem = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    this.dataset.dragReady = '0';
    this.classList.remove('dragging');
    draggedItem = null;
    renumberItems();
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const container = document.getElementById('checklistContainer');
    const afterElement = getDragAfterElement(container, e.clientY);
    
    if (afterElement == null) {
        container.appendChild(draggedItem);
    } else {
        container.insertBefore(draggedItem, afterElement);
    }
}

function handleDrop(e) {
    e.preventDefault();
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.checklist-item-card:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// ── Validation helpers ───────────────────────────────────────────────────────
function showValidationFlash(message, type = 'danger') {
    const toast = document.getElementById('validationToast');
    toast.className = `alert alert-${type} shadow`;
    document.getElementById('validationToastMsg').textContent = message;
    toast.classList.add('vt-show');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => {
        toast.classList.remove('vt-show');
    }, 2000);
}

function markInvalid(el) {
    if (!el) return;
    el.classList.add('field-invalid');
    const remove = () => {
        el.classList.remove('field-invalid');
        ['input', 'change', 'click'].forEach(ev => el.removeEventListener(ev, remove));
    };
    ['input', 'change', 'click'].forEach(ev => el.addEventListener(ev, remove));
}

function markGroupInvalid(container) {
    if (!container) return;
    container.classList.add('field-invalid');
    const remove = () => {
        container.classList.remove('field-invalid');
        ['click', 'input', 'change'].forEach(ev => container.removeEventListener(ev, remove));
    };
    ['click', 'input', 'change'].forEach(ev => container.addEventListener(ev, remove));
}


// Preview Function - Mirrors real examiner marking interface
function previewChecklist() {
    const cards = document.querySelectorAll('#checklistContainer > div');
    const hasItems = Array.from(cards).some(c => c.dataset.type === 'item');
    if (!hasItems) {
        alert('Add at least one checklist item to preview.');
        return;
    }

    const stationName = document.querySelector('input[name="name"]').value || 'Untitled Station';
    const duration = '8';
    
    // Gather scenario / instructions from the form
    const scenario = document.querySelector('textarea[name="scenario"]')?.value?.trim() || '';
    const instructions = document.querySelector('textarea[name="instructions"]')?.value?.trim() || '';

    // Build ILO id → number map from the first ilo-select's options
    const iloNumberMap = {};
    const firstIloSelect = document.querySelector('.checklist-item-card .ilo-select');
    if (firstIloSelect) {
        Array.from(firstIloSelect.options).forEach(opt => {
            if (opt.value) {
                const match = opt.text.match(/^(\d+)\./);
                if (match) iloNumberMap[opt.value] = parseInt(match[1], 10);
            }
        });
    }
    
    let previewHtml = `<html><head><title>Examiner Preview — ${stationName}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#F3F4F6;padding-bottom:100px}
        .evaluation-header{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);color:white;padding:12px 16px;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(0,0,0,0.3)}
        .station-name-large{font-size:1rem;font-weight:700;color:white;letter-spacing:0.3px;flex:1;text-align:center}
        .header-title{display:flex;align-items:center;gap:8px;margin-bottom:10px}
        .header-back-btn{display:flex;align-items:center;gap:4px;color:rgba(255,255,255,0.7);font-size:0.82rem;text-decoration:none;background:rgba(255,255,255,0.08);padding:4px 10px;border-radius:6px}
        .header-title-spacer{width:60px}
        .header-top{display:flex;justify-content:space-between;align-items:center;gap:12px}
        .info-labels{display:flex;gap:16px;flex-wrap:wrap}
        .info-label{display:flex;gap:6px;align-items:baseline}
        .label-text{font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;opacity:0.5;font-weight:600}
        .label-value{font-size:0.85rem;font-weight:600;color:white}
        .timer-widget{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,0.1);padding:6px 12px;border-radius:8px;font-family:'SF Mono',Monaco,monospace;font-size:1.4rem;font-weight:700;color:white;border:2px solid transparent}
        .content-wrapper{max-width:800px;margin:0 auto;padding:12px 12px 0}
        .demo-note{background:#fefce8;border:1.5px solid #fde047;padding:8px 14px;margin-bottom:10px;border-radius:8px;font-size:0.78rem;color:#713f12;display:flex;align-items:center;gap:6px}
        .section-divider{display:flex;align-items:center;margin:24px 0 12px}
        .section-label{display:inline-flex;align-items:center;gap:8px;font-size:0.78rem;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:1.5px;background:linear-gradient(135deg,#0d9488,#0f766e);padding:8px 36px 8px 18px;clip-path:polygon(0 0,calc(100% - 16px) 0,100% 50%,calc(100% - 16px) 100%,0 100%);box-shadow:2px 2px 8px rgba(13,148,136,0.3);white-space:nowrap}
        .section-line{flex:1;height:10px;background:linear-gradient(to right,#0d9488 0%,#5eead4 40%,#99f6e4 70%,transparent 100%);border-radius:0 100px 100px 0;opacity:0.6}
        .question-card{background:#fff;border:2px solid #E5E7EB;border-radius:12px;margin-bottom:10px;overflow:hidden;transition:all 0.3s;box-shadow:0 1px 2px rgba(0,0,0,0.06)}
        .question-card.answered{border-color:#10B981;background:#F0FDF4}
        .question-header{display:flex;justify-content:space-between;align-items:center;padding:6px 14px;background:#F9FAFB;border-bottom:1px solid #F3F4F6}
        .question-header-inner{display:flex;align-items:flex-start;gap:8px;width:100%}
        .question-number-badge{background:#494a4d;color:white;padding:2px 8px;border-radius:6px;font-size:0.7rem;font-weight:600;white-space:nowrap;margin-top:2px}
        .question-body{flex:1;line-height:1.6}
        .question-text-inline{font-size:1rem;line-height:1.6;color:#000;font-weight:500;display:inline}
        .marks-badge{display:inline-flex;align-items:center;font-size:0.65rem;font-weight:700;padding:0.1rem 0.45rem;border-radius:9999px;gap:3px;vertical-align:middle;margin-left:6px;white-space:nowrap;background:#fef3c7;color:#92400e;border:1px solid #fde68a}
        .evaluation-buttons{display:grid;gap:6px;padding:8px 12px;background:#F9FAFB;border-top:1px solid #E5E7EB}
        .eval-btn{padding:6px;font-size:0.82rem;font-weight:700;border:2px solid #D1D5DB;border-radius:6px;background:white;color:#374151;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px;min-height:48px;transition:all 0.1s}
        .eval-btn:hover{transform:translateY(-1px);box-shadow:0 2px 8px rgba(0,0,0,0.08)}
        .eval-btn.active{border-color:#0d9488;background:#0d9488;color:white}
        .eval-btn.score-zero.active{background:#EF4444;border-color:#EF4444}
        .eval-btn.full-pts.active{background:#10B981;border-color:#10B981}
        .eval-btn-icon{font-size:1rem}
        .eval-btn-label{font-size:0.78rem;line-height:1.2;text-align:center}
        .bottom-actions{position:fixed;bottom:0;left:0;right:0;background:white;padding:12px 16px;border-top:2px solid #E5E7EB;z-index:200}
        .action-buttons{max-width:800px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:12px}
        .btn-back{width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:#F3F4F6;border-radius:10px;color:#374151;font-size:1.2rem;text-decoration:none;border:2px solid #E5E7EB}
        .footer-total{display:flex;align-items:center;gap:10px}
        .total-mark{font-size:1.1rem;font-weight:600}
        .student-mark{font-size:1.5rem;font-weight:900;color:#111827}
        .mark-max{font-size:0.95rem;opacity:0.6;margin-left:4px;font-weight:600}
        .btn-submit{padding:12px 28px;background:linear-gradient(135deg,#0d9488,#0f766e);color:white;border:none;border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:8px}
        .progress-wrap{background:white;border-bottom:1px solid #E5E7EB;padding:8px 16px}
        .progress-row{display:flex;justify-content:space-between;font-size:0.75rem;color:#6B7280;margin-bottom:4px}
        .progress-bar{height:5px;background:#E5E7EB;border-radius:3px;overflow:hidden}
        .progress-fill{height:100%;background:#10B981;transition:width 0.3s}
                .case-card{background:#fff;border:2px solid #ccfbf1;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,0.06)}
        .case-title{font-size:1.1rem;font-weight:700;color:#0f766e;margin:0 0 12px 0;display:flex;align-items:center;gap:8px}
        .case-instructions{color:#374151;line-height:1.6;font-size:0.95rem}
        .case-instructions p{margin:0 0 8px 0;white-space:pre-wrap;word-break:break-word}
        .case-instructions p:last-child{margin-bottom:0}
        .ilo-badge,.marks-badge{display:inline-flex;align-items:center;font-size:0.65rem;font-weight:700;padding:0.1rem 0.45rem;border-radius:9999px;gap:3px;vertical-align:middle;margin-left:6px;white-space:nowrap;line-height:1.4}
        .ilo-badge{background:#dbeafe;color:#1e40af;border:1px solid #bfdbfe}
        .marks-badge{background:#fef3c7;color:#92400e;border:1px solid #fde68a}

    </style></head><body>
    <header class="evaluation-header">
        <div class="header-title">
            <a class="header-back-btn"><i class="bi bi-chevron-left"></i></a>
            <div class="station-name-large">${stationName}</div>
            <div class="header-title-spacer"></div>
        </div>
        <div class="header-top">
            <div class="info-labels">
                <div class="info-label"><span class="label-text">Student:</span><span class="label-value">Student Name</span></div>
                <div class="info-label"><span class="label-text">Reg No:</span><span class="label-value">11844785</span></div>
                <div class="info-label"><span class="label-text">Evaluator:</span><span class="label-value">Dr. Fawzi Yasin</span></div>
            </div>
            <div class="timer-widget"><i class="bi bi-clock"></i><span>${duration}:00</span></div>
        </div>
    </header>
    <div class="progress-wrap">
        <div class="progress-row"><span>Progress</span><span><span id="markedCount">0</span>/<span id="totalItems">0</span> marked</span></div>
        <div class="progress-bar"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
    </div>
    <div class="content-wrapper">
        <div class="demo-note"><i class="bi bi-hand-index"></i> Preview only — tap buttons to simulate marking</div>
        ${(scenario || instructions) ? `
        <div class="case-card">
            <h3 class="case-title"><i class="bi bi-file-text"></i> Case Scenario</h3>
            <div class="case-instructions">
                ${scenario ? `<p><strong>Scenario:</strong> ${scenario}</p>` : ''}
                ${instructions ? `<p><strong>Instructions:</strong> ${instructions}</p>` : ''}
            </div>
        </div>` : ''}
        <div id="checklistArea">`;
    
    let totalPts = 0;
    let itemNum = 0;

    cards.forEach((card) => {
        if (card.dataset.type === 'section') {
            const sectionTitle = card.querySelector('.section-title-input').value || 'Untitled Section';
            previewHtml += `<div class="section-divider"><div class="section-label"><i class="bi bi-folder2-open"></i> ${sectionTitle}</div><div class="section-line"></div></div>`;
        } else if (card.dataset.type === 'item') {
            const desc = card.querySelector('.item-description-input').value || '(No description)';
            const pts = getItemPoints(card) ?? 0;
            const qtype = card.querySelector('.question-type-select').value;

            // Get ILO and render ILO badge
            const iloId = card.querySelector('.ilo-select')?.value;
            const iloNum = iloId ? iloNumberMap[iloId] : null;
            const iloBadge = iloNum != null ? `<span class="ilo-badge"><i class="bi bi-tag-fill"></i> ILO ${iloNum}</span>` : '';

            // Collect image if available
            const imgThumb = card.querySelector('.img-preview-thumb');
            const rawSrc = imgThumb ? imgThumb.src : '';
            const imgSrc = rawSrc && rawSrc !== window.location.href && !rawSrc.endsWith('/') ? rawSrc : '';
            const imgHtml = imgSrc
                ? `<div style="padding:8px 16px 4px"><img src="${imgSrc}" style="max-width:100%;max-height:200px;object-fit:contain;border-radius:8px;border:1px solid #e5e7eb;background:#f8fafc;display:block" alt="Question image"></div>`
                : '';

            totalPts += pts;
            itemNum++;

            let answerHtml = '';
            if (qtype === 'mcq') {
                const mcq = getMcqData(card);
                answerHtml = `<div style="padding:8px 12px;background:#F9FAFB;border-top:1px solid #E5E7EB">`;
                mcq.options.forEach((opt, i) => {
                    const letter = String.fromCharCode(65 + i);
                    const isCorrect = i === mcq.correct_index;
                    answerHtml += `<label style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;cursor:pointer;border:2px solid ${isCorrect ? '#10B981' : '#E5E7EB'};margin-bottom:4px;background:${isCorrect ? '#F0FDF4' : 'white'};font-size:0.88rem">
                        <input type="radio" name="preview_mcq_${itemNum}" value="${i}" onclick="markMcq(${itemNum},${i},${i === mcq.correct_index ? pts : 0},${pts})">
                        <span style="font-weight:700;color:#6c757d;min-width:18px">${letter}.</span>
                        <span>${opt || '(empty)'}</span>
                        ${isCorrect ? '<span style="margin-left:auto;font-size:0.7rem;color:#10B981;font-weight:700">✓ CORRECT</span>' : ''}
                    </label>`;
                });
                answerHtml += `</div>`;
            } else {
                const key = getKeyAnswer(card);
                answerHtml = `<div style="padding:8px 12px;background:#F9FAFB;border-top:1px solid #E5E7EB">
                    <div style="font-size:0.75rem;font-weight:700;color:#198754;margin-bottom:4px"><i class="bi bi-key"></i> Key Answer</div>
                    <div style="background:#f0fff4;border:1px solid #a3cfbb;padding:6px 10px;border-radius:6px;font-size:0.88rem;color:#155724">${key || '<em style="color:#6c757d">No key answer entered</em>'}</div>
                    <textarea style="width:100%;margin-top:8px;padding:6px 8px;border:1px solid #dee2e6;border-radius:4px;font-size:0.85rem;resize:vertical;min-height:50px" placeholder="Student answer..." oninput="markEssay(${itemNum},this.value.trim() ? ${pts} : 0,${pts})"></textarea>
                </div>`;
            }

            previewHtml += `<div class="question-card" id="item-${itemNum}">
                <div class="question-header"><div class="question-header-inner">
                    <span class="question-number-badge">${qtype === 'mcq' ? 'MCQ' : 'SAQ'} ${itemNum}</span>
                    <div class="question-body">
                        <span class="question-text-inline">${desc}</span>${iloBadge}<span class="marks-badge"><i class="bi bi-star-fill"></i> ${pts} pt${pts !== 1 ? 's' : ''}</span>
                    </div>
                </div></div>
                ${imgHtml}
                ${answerHtml}
            </div>`;
        }
    });

    previewHtml += `</div></div>
    <div class="bottom-actions"><div class="action-buttons">
        <a class="btn-back"><i class="bi bi-arrow-left"></i></a>
        <div class="footer-total"><div class="total-mark"><span class="student-mark" id="currentScore">0.00</span><span class="mark-max">/${totalPts.toFixed(2)}</span></div></div>
        <button class="btn-submit"><i class="bi bi-check-circle"></i> Submit Evaluation</button>
    </div></div>
    <` + `script>
    let scores = {};
    const totalItems = ${itemNum};
    document.getElementById('totalItems').textContent = totalItems;
    function updateScore() {
        let cur = 0, marked = 0;
        for (let id in scores) { cur += scores[id]; marked++; }
        document.getElementById('currentScore').textContent = cur.toFixed(2);
        document.getElementById('markedCount').textContent = marked;
        document.getElementById('progressFill').style.width = (marked / totalItems * 100) + '%';
    }
    function markMcq(itemId, optIdx, score, maxPts) {
        scores[itemId] = score;
        document.getElementById('item-' + itemId).classList.add('answered');
        updateScore();
    }
    function markEssay(itemId, score, maxPts) {
        scores[itemId] = score;
        document.getElementById('item-' + itemId).classList.toggle('answered', score > 0);
        updateScore();
    }
    <` + `/script></body></html>`;

    const previewWindow = window.open('', 'Preview', 'width=540,height=750');
    previewWindow.document.write(previewHtml);
    previewWindow.document.close();
}
