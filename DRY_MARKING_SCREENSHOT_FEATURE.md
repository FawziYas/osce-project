# Dry Marking Screenshot to Telegram Feature

## Overview
This document contains all code added for the dry marking page screenshot PDF → Telegram feature. Use this to easily remove the feature if needed.

**Feature**: When a student submits dry marking answers, a screenshot of the page is automatically captured as a PDF (using html2canvas + jsPDF), and sent to a Telegram channel.

---

## 1. Template Changes: `templates/examiner/Dry_marking.html`

### 1a. Add CDN Scripts to `{% block head %}` (after line 10)

Add these two script tags in the `{% block head %}` section:

```html
<!-- Page screenshot libraries -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js" integrity="sha512-qZvrmS2ekKPF2mSznTQsxqPgnpkI4DNTlrdUmTzrDgektczlKNRRhy5X5AAOnx5S09ydFYWWNSfcEqDTTHgtNA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
```

**To remove**: Delete these two `<script>` tags entirely.

---

### 1b. Add `captureAndUploadPdf()` Function in `{% block scripts %}`

Add this entire function in the `{% block scripts %}` section (before `showConfirmModal()`):

```javascript
// ============================================================================
// PAGE SCREENSHOT → PDF → TELEGRAM
// ============================================================================

async function captureAndUploadPdf() {
    if (typeof html2canvas === 'undefined' || typeof window.jspdf === 'undefined') {
        console.warn('html2canvas / jsPDF not loaded — skipping screenshot.');
        return;
    }

    try {
        // Exit fullscreen so the full page is capturable
        if (document.fullscreenElement) {
            await document.exitFullscreen().catch(() => {});
        }

        // Scroll to top for a clean capture
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 300));

        const canvas = await html2canvas(document.body, {
            scale: 2,
            useCORS: true,
            allowTaint: false,
            scrollX: 0,
            scrollY: 0,
            windowWidth: document.documentElement.scrollWidth,
            windowHeight: document.documentElement.scrollHeight,
            ignoreElements: (el) =>
                el.id === 'confirm-modal' ||
                el.id === 'warn-modal' ||
                el.id === 'submit-btn' ||
                el.id === 'submit-success-overlay' ||
                el.classList.contains('confirm-modal') ||
                el.classList.contains('warn-modal'),
        });

        const { jsPDF } = window.jspdf;
        const imgData  = canvas.toDataURL('image/jpeg', 0.92);
        const pdfWidth  = 210;   // A4 mm
        const pdfHeight = 297;
        const imgHeight = (canvas.height * pdfWidth) / canvas.width;

        const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
        let heightLeft = imgHeight;
        let position   = 0;

        pdf.addImage(imgData, 'JPEG', 0, position, pdfWidth, imgHeight);
        heightLeft -= pdfHeight;

        while (heightLeft > 0) {
            position -= pdfHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'JPEG', 0, position, pdfWidth, imgHeight);
            heightLeft -= pdfHeight;
        }

        const pdfBlob = pdf.output('blob');

        // Upload screenshot PDF to server → Telegram
        const formData = new FormData();
        formData.append('pdf_file', pdfBlob, 'screenshot.pdf');

        const resp = await fetch(MARKING_DATA.pdfUploadUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': MARKING_DATA.csrfToken },
            credentials: 'same-origin',
            body: formData,
        });

        if (resp.ok) {
            const res = await resp.json();
            console.log('Screenshot PDF sent to Telegram:', res.filename);
        } else {
            const err = await resp.json().catch(() => ({}));
            console.error('Screenshot PDF upload failed:', err);
        }
    } catch (err) {
        // Never block navigation on PDF errors
        console.error('captureAndUploadPdf error:', err);
    }
}
```

**To remove**: Delete the entire `captureAndUploadPdf()` function.

---

### 1c. Modify `confirmSubmit()` Success Block

Replace the `if (result.success)` block in `confirmSubmit()` with:

```javascript
        if (result.success) {
            if (examTimer) examTimer.stop();
            scoreIsSubmitted = true;

            // Show a clear success overlay immediately — student knows it worked.
            const overlay = document.createElement('div');
            overlay.id = 'submit-success-overlay';
            overlay.style.cssText = [
                'position:fixed', 'inset:0', 'z-index:9999',
                'background:rgba(17,24,39,0.85)',
                'display:flex', 'flex-direction:column',
                'align-items:center', 'justify-content:center', 'gap:16px',
            ].join(';');
            overlay.innerHTML = `
                <div style="width:64px;height:64px;border-radius:50%;
                     background:#22c55e;display:flex;align-items:center;justify-content:center;">
                  <svg width="34" height="34" viewBox="0 0 24 24" fill="none"
                       stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
                <p style="color:#fff;font-size:1.25rem;font-weight:600;margin:0;">
                    Submitted successfully!
                </p>
                <p style="color:#9ca3af;font-size:0.9rem;margin:0;">
                    Saving your report&hellip;
                </p>`;
            document.body.appendChild(overlay);

            // Capture the page as a screenshot PDF behind the overlay and upload.
            await captureAndUploadPdf();

            // Navigate away.
            if (window.opener && !window.opener.closed) {
                window.opener.location.href = "{% url 'examiner:station_dashboard' assignment.id %}";
                window.close();
            } else {
                window.location.replace("{% url 'examiner:station_dashboard' assignment.id %}");
            }
```

**To remove**: Replace this block with the original non-screenshot version:

```javascript
        if (result.success) {
            if (examTimer) examTimer.stop();
            scoreIsSubmitted = true;

            // Navigate away.
            if (window.opener && !window.opener.closed) {
                window.opener.location.href = "{% url 'examiner:station_dashboard' assignment.id %}";
                window.close();
            } else {
                window.location.replace("{% url 'examiner:station_dashboard' assignment.id %}");
            }
```

---

## 2. Backend Changes: `examiner/views/api.py`

### Replace the entire `save_dry_pdf` view (lines ~838-910)

```python
@login_required
@require_POST
def save_dry_pdf(request, score_id):
    """
    Receive a screenshot PDF of the dry-marking page (captured client-side
    with html2canvas + jsPDF) and forward it to Telegram.
    """
    import re
    import logging
    log = logging.getLogger(__name__)

    score = get_object_or_404(
        StationScore.objects.select_related(
            'session_student__session__exam',
            'session_student__session',
            'station',
        ),
        pk=score_id,
        examiner=request.user,
    )

    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file:
        return JsonResponse({'success': False, 'error': 'No PDF file received.'}, status=400)

    if pdf_file.size > 50 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'PDF too large (max 50 MB).'}, status=400)

    pdf_bytes = pdf_file.read()

    # Build filename: "Student Name - Exam Name - Session Name.pdf"
    def _safe(s):
        return re.sub(r'[\\/:*?"<>|]+', '_', str(s)).strip()

    student_name = _safe(score.session_student.full_name or 'Unknown')
    try:
        exam_name = _safe(score.session_student.session.exam.name)
    except AttributeError:
        exam_name = 'Exam'
    try:
        session_name = _safe(score.session_student.session.name)
    except AttributeError:
        session_name = 'Session'

    filename = f'{student_name} - {exam_name} - {session_name}.pdf'

    try:
        from examiner.google_drive import upload_pdf
        file_id = upload_pdf(pdf_bytes, filename)
    except Exception as exc:
        log.error('Telegram upload failed: %s', exc, exc_info=True)
        return JsonResponse({'success': False, 'error': f'Upload failed: {exc}'}, status=500)

    return JsonResponse({'success': True, 'file_id': file_id, 'filename': filename})
```

**To remove**: Delete this entire view function or replace with a stub that returns `{'success': True}`.

---

## 3. Settings: `osce_project/settings/base.py`

### Add these two lines (usually near other authentication settings)

```python
TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_CHAT_ID = env('TELEGRAM_CHAT_ID', default='')
```

**To remove**: Delete these two lines entirely.

---

## 4. Environment Variables: `.env` (Local only, not in git)

### Add/update these lines in your `.env` file

```
TELEGRAM_BOT_TOKEN=<your bot token from @BotFather>
TELEGRAM_CHAT_ID=<your channel ID, negative number>
```

**To remove**: Delete these two lines from `.env`.

---

## 5. Module: `examiner/google_drive.py` (Already exists)

This file contains the `upload_pdf()` function that sends the PDF to Telegram. It was created as part of this feature.

**To remove**: Delete the entire `examiner/google_drive.py` file if not used elsewhere.

---

## 6. URL Registration: `examiner/urls.py` (Verify it exists)

The URL pattern should already be registered:

```python
path('dry-mark/save-pdf/<uuid:score_id>/', api.save_dry_pdf, name='save_dry_pdf')
```

**Note**: Check if this URL is needed by other features before removing.

---

## 7. CSP Middleware: `core/middleware.py` (Verify it includes)

The CSP should allow these domains (usually already present):

```python
"script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
```

**To verify/remove**: Check if `cdnjs.cloudflare.com` is still needed by other features.

---

## Summary: Step-by-Step Removal

To completely remove this feature:

1. **Delete from `templates/examiner/Dry_marking.html`**:
   - Remove the two CDN `<script>` tags
   - Remove the entire `captureAndUploadPdf()` function
   - Restore the original `confirmSubmit()` success block (simpler version without overlay)

2. **Replace in `examiner/views/api.py`**:
   - Delete the entire `save_dry_pdf` view or replace with stub

3. **Delete from `osce_project/settings/base.py`**:
   - Remove the two `TELEGRAM_*` lines

4. **Remove from `.env`**:
   - Delete the two `TELEGRAM_*` environment variables

5. **Optionally delete**:
   - `examiner/google_drive.py` (if not used elsewhere)

6. **Verify** (optional cleanup):
   - Remove `cdnjs.cloudflare.com` from CSP if not needed elsewhere
   - Remove URL pattern from `examiner/urls.py` if not needed elsewhere

---

## Testing After Removal

After removing the feature, test:
- Student can still submit dry marking
- No console errors about undefined `html2canvas` or `jsPDF`
- Navigation after submit works normally
