/* ═══════════════════════════════════════════════════════
   Dry Exam Verification Modal – JavaScript
   Two modes:
     • Registration Number (default) – correct reg → redirect
     • Master Key (toggle) – correct password → redirect
   ═══════════════════════════════════════════════════════ */
(function () {
    'use strict';

    /* ── DOM refs ─────────────────────────────────────── */
    const modal = document.getElementById('verifyExamModal');
    if (!modal) return;

    const bsModal = new bootstrap.Modal(modal, {
        backdrop: 'static',
        keyboard: false,
    });

    const inputLabel    = modal.querySelector('#verifyInputLabel');
    const inputIconLeft = modal.querySelector('#verifyInputIconLeft');
    const input         = modal.querySelector('#verifyInput');
    const clearBtn      = modal.querySelector('#verifyClearBtn');
    const pwdToggle     = modal.querySelector('#verifyPwdToggle');
    const statusIcon    = modal.querySelector('#verifyStatusIcon');
    const feedback      = modal.querySelector('#verifyFeedback');
    const modeToggle    = modal.querySelector('#verifyModeToggle');
    const modeLink      = modal.querySelector('#verifyModeLink');
    const btnSubmit     = modal.querySelector('#verifyBtnSubmit');

    /* ── State ────────────────────────────────────────── */
    let state = {};

    function resetState() {
        state = {
            studentId: null,
            sessionId: null,
            assignmentId: null,
            verifyUrl: null,
            masterKeyUrl: null,
            mode: 'reg',        // 'reg' or 'masterkey'
            busy: false,
            redirectUrl: null,
        };
    }

    /* ── CSRF helper ──────────────────────────────────── */
    function getCookie(name) {
        const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return v ? v.pop() : '';
    }
    const csrfToken = getCookie('csrftoken')
        || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
        || '';

    /* ── Utility helpers ──────────────────────────────── */
    function shake(el) {
        el.classList.remove('verify-shake');
        void el.offsetWidth;
        el.classList.add('verify-shake');
    }

    function setInputBorder(validState) {
        input.classList.remove('border-success', 'border-danger');
        if (validState === true) input.classList.add('border-success');
        else if (validState === false) input.classList.add('border-danger');
    }

    function setIconSpinner() {
        statusIcon.innerHTML = '<span class="spinner-border text-secondary" role="status"></span>';
    }
    function setIconCheck() {
        statusIcon.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
    }
    function setIconClear() {
        statusIcon.innerHTML = '';
    }

    function setFeedback(text, cls) {
        feedback.className = 'verify-feedback ' + cls;
        feedback.innerHTML = text;
    }

    /* ── Mode switching (reg ↔ masterkey) ─────────────── */
    function applyRegMode() {
        state.mode = 'reg';
        input.value = '';
        input.type = 'text';
        input.placeholder = 'Enter Your University ID ';
        inputLabel.textContent = 'ID University Number';
        inputIconLeft.className = 'bi bi-person-badge input-icon-left';
        modeLink.innerHTML = '<i class="bi bi-key-fill"></i> Use Master Key instead';
        clearBtn.classList.add('d-none');
        pwdToggle.classList.add('d-none');
        setInputBorder(null);
        setIconClear();
        setFeedback('', '');
        input.readOnly = false;
        input.disabled = false;
        input.focus();
    }

    function applyMasterKeyMode() {
        state.mode = 'masterkey';
        input.value = '';
        input.type = 'password';
        input.placeholder = 'Enter master key';
        inputLabel.textContent = 'Master Key';
        inputIconLeft.className = 'bi bi-key-fill input-icon-left';
        modeLink.innerHTML = '<i class="bi bi-person-badge"></i> Use Id Number instead';
        clearBtn.classList.add('d-none');
        pwdToggle.classList.remove('d-none');
        pwdToggle.innerHTML = '<i class="bi bi-eye"></i>';
        setInputBorder(null);
        setIconClear();
        setFeedback('', '');
        input.readOnly = false;
        input.disabled = false;
        input.focus();
    }

    modeLink.addEventListener('click', function (e) {
        e.preventDefault();
        if (state.busy) return;
        if (state.mode === 'reg') applyMasterKeyMode();
        else applyRegMode();
    });

    btnSubmit.addEventListener('click', function () {
        if (state.mode === 'reg') verifyRegistration();
        else verifyMasterKey();
    });

    /* ── Open modal from "Start Exam" button ─────────── */
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-start-dry-exam');
        if (!btn) return;
        e.preventDefault();

        resetState();
        state.studentId    = btn.dataset.studentId;
        state.sessionId    = btn.dataset.sessionId;
        state.assignmentId = btn.dataset.assignmentId;
        state.verifyUrl    = btn.dataset.verifyUrl;
        state.masterKeyUrl = btn.dataset.masterkeyUrl;

        // Reset UI to reg mode
        applyRegMode();

        bsModal.show();
        setTimeout(function () { input.focus(); }, 300);
    });

    /* ── Verify Registration Number ──────────────────── */
    function verifyRegistration() {
        const val = input.value.trim();
        if (!val || state.busy) return;
        state.busy = true;

        setIconSpinner();
        setFeedback('<span class="spinner-border"></span> Verifying...', 'text-muted');
        input.disabled = true;
        btnSubmit.disabled = true;

        fetch(state.verifyUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_number: val,
                student_id: state.studentId,
                session_id: state.sessionId,
                assignment_id: state.assignmentId,
            }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            state.busy = false;

            if (data.valid) {
                state.redirectUrl = data.redirect_url;
                setInputBorder(true);
                setIconCheck();
                const confirmMsg = `<i class="bi bi-check-circle-fill"></i> <strong>${data.student_name}</strong> (${data.student_number})<br><small>Starting exam...</small>`;
                setFeedback(confirmMsg, 'text-success');
                input.readOnly = true;
                modeToggle.classList.add('d-none');
                performRedirect();
            } else {
                input.disabled = false;
                btnSubmit.disabled = false;
                setInputBorder(false);
                setIconClear();
                setFeedback(data.message || 'Registration number does not match.', 'text-danger');
                shake(input.closest('.verify-input-wrap'));
                input.focus();
            }
        })
        .catch(function () {
            input.disabled = false;
            btnSubmit.disabled = false;
            state.busy = false;
            setIconClear();
            setFeedback('Network error. Please try again.', 'text-danger');
        });
    }

    /* ── Verify Master Key ───────────────────────────── */
    function verifyMasterKey() {
        const pwd = input.value;
        if (!pwd || state.busy) return;
        state.busy = true;

        setIconSpinner();
        setFeedback('<span class="spinner-border"></span> Verifying...', 'text-muted');
        input.disabled = true;
        btnSubmit.disabled = true;

        fetch(state.masterKeyUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: pwd,
                student_id: state.studentId,
                session_id: state.sessionId,
                assignment_id: state.assignmentId,
            }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            state.busy = false;

            if (data.valid) {
                state.redirectUrl = data.redirect_url;
                setInputBorder(true);
                setIconCheck();
                const confirmMsg = `<i class="bi bi-check-circle-fill"></i> <strong>${data.student_name}</strong> (${data.student_number})<br><small>Starting exam...</small>`;
                setFeedback(confirmMsg, 'text-success');
                input.readOnly = true;
                pwdToggle.classList.add('d-none');
                modeToggle.classList.add('d-none');
                performRedirect();
            } else {
                input.disabled = false;
                btnSubmit.disabled = false;
                setInputBorder(false);
                setIconClear();
                setFeedback(data.message || 'Incorrect password.', 'text-danger');
                shake(input.closest('.verify-input-wrap'));
                input.focus();
            }
        })
        .catch(function () {
            input.disabled = false;
            btnSubmit.disabled = false;
            state.busy = false;
            setIconClear();
            setFeedback('Network error. Please try again.', 'text-danger');
        });
    }

    /* ── Input events ────────────────────────────────── */
    let debounceTimer = null;

    input.addEventListener('input', function () {
        if (state.mode === 'reg') {
            clearBtn.classList.toggle('d-none', !input.value);
        }
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            clearTimeout(debounceTimer);
            if (state.mode === 'reg') verifyRegistration();
            else verifyMasterKey();
        }
    });

    clearBtn.addEventListener('click', function () {
        input.value = '';
        input.focus();
        clearBtn.classList.add('d-none');
        setInputBorder(null);
        setFeedback('', '');
    });

    pwdToggle.addEventListener('click', function () {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        pwdToggle.innerHTML = isPassword
            ? '<i class="bi bi-eye-slash"></i>'
            : '<i class="bi bi-eye"></i>';
    });

    /* ── Redirect ────────────────────────────────────── */
    function performRedirect() {
        setTimeout(function () {
            window.location.href = state.redirectUrl;
        }, 600);
    }

    /* ── Reset on modal hidden ───────────────────────── */
    modal.addEventListener('hidden.bs.modal', function () {
        resetState();
        input.readOnly = false;
        input.disabled = false;
        btnSubmit.disabled = false;
        modeToggle.classList.remove('d-none');
    });

})();
