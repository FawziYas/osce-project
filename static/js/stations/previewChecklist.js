/* Shared preview popup rendering for station/template builders. */

function previewChecklist() {
    const cards = document.querySelectorAll('#checklistContainer > div');
    const hasItems = Array.from(cards).some(c => c.dataset.type === 'item');
    if (!hasItems) {
        alert('Add at least one checklist item to preview.');
        return;
    }

    const previewName = document.querySelector('input[name="name"]')?.value || 'Untitled';
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

    let previewHtml = `<html><head><title>Examiner Preview - ${previewName}</title>
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
            <div class="station-name-large">${previewName}</div>
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
        <div class="demo-note"><i class="bi bi-hand-index"></i> Preview only - tap buttons to simulate marking</div>
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
            const scale = card.querySelector('.scale-select').value;
            const scaleInfo = SCALES[scale];
            const scaleLabels = scaleInfo ? scaleInfo.labels : ['Not Done', 'Done'];

            const iloId = card.querySelector('.ilo-select')?.value;
            const iloNum = iloId ? iloNumberMap[iloId] : null;
            const iloBadge = iloNum != null ? `<span class="ilo-badge"><i class="bi bi-tag-fill"></i> ILO ${iloNum}</span>` : '';

            totalPts += pts;
            itemNum++;

            const nLabels = scaleLabels.length;
            const colCount = Math.min(nLabels, 4);
            let buttonsHtml = `<div class="evaluation-buttons" style="grid-template-columns:repeat(${colCount},1fr)">`;
            scaleLabels.forEach((label, i) => {
                const score = nLabels === 1 ? pts : parseFloat((i / (nLabels - 1) * pts).toFixed(2));
                const shortLabel = label.replace(/\([^)]+\)/g, '').trim();
                let btnClass = 'eval-btn';
                let iconClass = 'bi-dash-circle';
                if (i === 0) { btnClass += ' score-zero'; iconClass = 'bi-x-circle'; }
                else if (i === nLabels - 1) { btnClass += ' full-pts'; iconClass = 'bi-check-circle'; }
                buttonsHtml += `<button class="${btnClass}" onclick="markItem(${itemNum},${score},${pts},this)"><span class="eval-btn-icon"><i class="bi ${iconClass}"></i></span><span class="eval-btn-label">${shortLabel}</span></button>`;
            });
            buttonsHtml += '</div>';

            previewHtml += `<div class="question-card" id="item-${itemNum}"><div class="question-header"><div class="question-header-inner"><span class="question-number-badge">Q${itemNum}</span><div class="question-body"><span class="question-text-inline">${desc}</span>${iloBadge}<span class="marks-badge"><i class="bi bi-star-fill"></i> ${pts} pt${pts !== 1 ? 's' : ''}</span></div></div></div>${buttonsHtml}</div>`;
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
    function markItem(itemId, score, maxPts, btn) {
        scores[itemId] = parseFloat(score);
        const card = document.getElementById('item-' + itemId);
        card.classList.add('answered');
        card.querySelectorAll('.eval-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        let cur = 0, marked = 0;
        for (let id in scores) { cur += scores[id]; marked++; }
        document.getElementById('currentScore').textContent = cur.toFixed(2);
        document.getElementById('markedCount').textContent = marked;
        document.getElementById('progressFill').style.width = (marked / totalItems * 100) + '%';
    }
    <` + `/script></body></html>`;

    const previewWindow = window.open('', 'Preview', 'width=540,height=750');
    previewWindow.document.write(previewHtml);
    previewWindow.document.close();
}
