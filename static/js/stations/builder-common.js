/* Shared builder helpers for form_simple + template_form. */

function addNewItem(description = '', points = null, scale = 'binary', iloId = '', customLabels = null, startCollapsed = false) {
    const container = document.getElementById('checklistContainer');
    const template = document.getElementById('itemTemplate');
    const clone = template.content.cloneNode(true);

    itemCounter++;
    const itemCard = clone.querySelector('.checklist-item-card');
    itemCard.dataset.itemId = itemCounter;

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

    clone.querySelector('.scale-select').value = scale;
    clone.querySelector('.ilo-select').value = iloId || '';

    container.appendChild(clone);

    const addedCard = container.lastElementChild;
    if (startCollapsed) {
        addedCard.classList.add('collapsed');
    }

    if (scale === 'custom' && customLabels) {
        const customEditor = addedCard.querySelector('.custom-scale-editor');
        const levelSelect = addedCard.querySelector('.level-count-select');
        customEditor.classList.add('visible');
        levelSelect.value = customLabels.length;

        const labelsContainer = addedCard.querySelector('.custom-labels-container');
        let html = '';
        customLabels.forEach((label, i) => {
            html += `<div class="custom-label-row">
                <span class="level-num">${i}:</span>
                <input type="text" class="custom-label" data-level="${i}" value="${label}">
            </div>`;
        });
        labelsContainer.innerHTML = html;
    }

    setupDragDrop(addedCard);

    if (!description) {
        addedCard.querySelector('.item-description-input').focus();
    }

    renumberItems();
    updateSummary();
}

function toggleItemFold(btn) {
    btn.closest('.checklist-item-card').classList.toggle('collapsed');
}

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
    // Drag must be armed by pressing the drag handle first.
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
    const draggableElements = [...container.querySelectorAll('.checklist-item-card:not(.dragging), .section-header-card:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;

        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        }
        return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}
