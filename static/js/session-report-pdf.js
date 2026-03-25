/**
 * session-report-pdf.js  (HTML print edition)
 * ─────────────────────────────────────────────────────────────────────────────
 * OSCE Session Report – generates a print-ready HTML window so the browser
 * renders Arabic text natively (HarfBuzz / DirectWrite) — always connected,
 * always correct — without any custom shaping code.
 *
 * Entry point:  window.generateSessionReport(sessionId, meta)
 *   meta = { sessionName, sessionDate, sessionStatus, examName,
 *             courseName, department }
 *
 * Data sources (existing REST endpoints, no backend changes needed):
 *   GET /api/creator/sessions/<id>/paths         → paths + stations + students
 *   GET /api/creator/sessions/<id>/assignments   → examiner ↔ station map
 *   GET /api/creator/examiners                   → examiner details
 * ─────────────────────────────────────────────────────────────────────────────
 */
(function (global) {
    'use strict';

    /* ── helpers ──────────────────────────────────────────────────────────── */
    function fmtDate(s) {
        if (!s) return 'N/A';
        try {
            const d = new Date(s);
            return isNaN(d) ? s : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
        } catch (_) { return s; }
    }

    function fmtNow() {
        return new Date().toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function capitalize(str) {
        return (str || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    function genReportId(id) {
        const r = Math.random().toString(36).substring(2, 6).toUpperCase();
        return 'RPT-' + r + '-' + (id || 'XXXX').toString().substring(0, 8).toUpperCase();
    }

    function safeFilename(str) {
        return (str || 'session').replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_') || 'session';
    }

    /** True if the string contains Arabic-script characters. */
    function hasArabic(str) {
        return /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/.test(str || '');
    }

    /** Decode \uXXXX sequences emitted by Django's |escapejs filter. */
    function unescapeJs(str) {
        if (!str) return '';
        return String(str).replace(/\\u([0-9a-fA-F]{4})/g, function (_, h) {
            return String.fromCharCode(parseInt(h, 16));
        });
    }

    /** Escape HTML special characters. */
    function esc(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Wrap a value in a span that applies RTL + Arabic font when the text
     * contains Arabic characters — the browser then shapes it natively.
     */
    function arabicCell(val) {
        var s = esc(val);
        return hasArabic(val) ? '<span class="ar">' + s + '</span>' : s;
    }

    /** Fetch JSON, checking Content-Type to catch session-expired redirects. */
    async function fetchJSON(url) {
        var res = await fetch(url, { credentials: 'same-origin' });
        var ct  = res.headers.get('content-type') || '';
        if (!ct.includes('application/json')) {
            throw new Error(
                'Session expired \u2014 the server returned an HTML page instead of JSON.\n' +
                'Please refresh the page and log in again.'
            );
        }
        if (!res.ok) { throw new Error('API error ' + res.status + ' at ' + url); }
        return res.json();
    }

    /* ── Status badge colours ────────────────────────────────────────────── */
    var STATUS_CSS = {
        scheduled:   '#3c6fa8',
        in_progress: '#16a062',
        completed:   '#2980b9',
        archived:    '#646e78',
        cancelled:   '#c0392b',
    };

    /* ── CSS for the print window ─────────────────────────────────────────── */
    function buildCSS() {
        return [
        '*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }',
        ':root {',
        '    --navy:   #1a3a5c;',
        '    --navy2:  #26507a;',
        '    --accent: #29b6f6;',
        '    --white:  #ffffff;',
        '    --lgray:  #f5f7fa;',
        '    --mgray:  #c8d2dc;',
        '    --dgray:  #646e78;',
        '}',
        'body {',
        '    font-family: "Segoe UI", Arial, "Helvetica Neue", sans-serif;',
        '    font-size: 10pt;',
        '    color: #282832;',
        '    background: #fff;',
        '}',
        '/* Arabic text \u2013 browser renders it natively, connected and correct */',
        '.ar {',
        '    font-family: "Amiri", "Noto Naskh Arabic", "Traditional Arabic",',
        '                 "Arabic Typesetting", "Simplified Arabic", Arial, sans-serif;',
        '    direction: rtl;',
        '    unicode-bidi: embed;',
        '    display: inline-block;',
        '}',
        '/* ---- header ---- */',
        '.rpt-header {',
        '    background: var(--navy);',
        '    color: var(--white);',
        '    padding: 12px 18px 0;',
        '    border-bottom: 3px solid var(--accent);',
        '}',
        '.rpt-header-top {',
        '    display: flex;',
        '    align-items: center;',
        '    justify-content: space-between;',
        '    padding-bottom: 10px;',
        '}',
        '.rpt-logo-area { display: flex; align-items: center; gap: 12px; }',
        '.rpt-logo-box {',
        '    width: 46px; height: 38px;',
        '    border: 2px solid rgba(255,255,255,.25);',
        '    border-radius: 5px;',
        '    display: flex; flex-direction: column;',
        '    align-items: center; justify-content: center;',
        '    background: rgba(255,255,255,.08);',
        '}',
        '.rpt-logo-box .logo-main { font-size: 13pt; font-weight: 700; letter-spacing: 1px; }',
        '.rpt-logo-box .logo-sub  { font-size: 6.5pt; opacity: .7; letter-spacing: 2px; }',
        '.rpt-title-area h1 { font-size: 16pt; font-weight: 700; margin: 0; }',
        '.rpt-title-area p  { font-size: 8pt; color: rgba(255,255,255,.65); margin: 2px 0 0; }',
        '.rpt-meta { text-align: right; font-size: 7.5pt; color: rgba(200,225,245,.9); line-height: 1.6; }',
        '.rpt-meta strong { font-size: 8pt; color: #fff; }',
        '/* ---- section titles ---- */',
        '.section-title {',
        '    background: var(--navy);',
        '    color: var(--white);',
        '    font-size: 10pt; font-weight: 700;',
        '    padding: 5px 12px 5px 18px;',
        '    margin: 18px 0 10px;',
        '    border-left: 5px solid var(--accent);',
        '    page-break-after: avoid;',
        '}',
        '/* ---- info cards ---- */',
        '.cards-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }',
        '.info-card {',
        '    flex: 1; min-width: 120px;',
        '    background: var(--lgray);',
        '    border: 1px solid var(--mgray);',
        '    border-radius: 4px;',
        '    padding: 7px 9px;',
        '}',
        '.info-card .card-label { font-size: 6.5pt; color: var(--dgray); margin-bottom: 3px; }',
        '.info-card .card-value {',
        '    font-size: 9.5pt; font-weight: 700; color: var(--navy);',
        '    word-break: break-word; line-height: 1.3;',
        '}',
        '.info-card.status-card { background: var(--navy); }',
        '.info-card.status-card .card-label { color: rgba(255,255,255,.75); }',
        '.info-card.status-card .card-value { color: #fff; font-size: 10pt; }',
        '/* ---- tables ---- */',
        'table { width: 100%; border-collapse: collapse; font-size: 8.5pt; margin-bottom: 4px; page-break-inside: auto; }',
        'thead { display: table-header-group; }',
        'tr { page-break-inside: avoid; }',
        'th {',
        '    background: var(--navy); color: var(--white);',
        '    text-align: center; font-weight: 600;',
        '    padding: 5px 6px; font-size: 8pt;',
        '    border: 1px solid #26507a;',
        '}',
        'td { padding: 4.5px 6px; border: 1px solid var(--mgray); vertical-align: middle; }',
        'tr:nth-child(even) td { background: var(--lgray); }',
        '/* Arabic table cells */',
        'td.arc {',
        '    text-align: right; direction: rtl;',
        '    font-family: "Amiri","Noto Naskh Arabic","Traditional Arabic","Arabic Typesetting",Arial,sans-serif;',
        '}',
        '.tc { text-align: center; }',
        '.tl { text-align: left; }',
        '/* ---- path sub-headers ---- */',
        '.path-header {',
        '    background: var(--navy2); color: var(--white);',
        '    font-weight: 600; font-size: 8.5pt;',
        '    padding: 5px 9px;',
        '    border-radius: 3px 3px 0 0;',
        '    margin-top: 10px;',
        '    page-break-after: avoid;',
        '}',
        '.no-data { font-style: italic; color: var(--dgray); font-size: 8.5pt; padding: 6px 4px; }',
        '/* ---- footer ---- */',
        '.rpt-footer {',
        '    margin-top: 24px;',
        '    border-top: 1px solid var(--mgray);',
        '    background: var(--lgray);',
        '    padding: 7px 16px;',
        '    font-size: 6.5pt; color: var(--dgray);',
        '    display: flex; justify-content: space-between; align-items: center;',
        '}',
        '.rpt-footer .conf { text-align: center; flex: 1; font-style: italic; }',
        '/* ---- print controls bar (hidden when printing) ---- */',
        '.print-controls {',
        '    background: #e8f0fe;',
        '    border-bottom: 2px solid var(--accent);',
        '    padding: 10px 16px;',
        '    display: flex; align-items: center; gap: 10px;',
        '    position: sticky; top: 0; z-index: 100;',
        '}',
        '.print-controls button {',
        '    padding: 7px 20px; border: none; border-radius: 4px;',
        '    cursor: pointer; font-size: 9.5pt; font-weight: 600;',
        '}',
        '.btn-print  { background: var(--navy); color: #fff; }',
        '.btn-close-w { background: #8899aa; color: #fff; }',
        '/* ---- @page / @media print ---- */',
        '@page { size: A4 portrait; margin: 20mm 15mm 25mm 15mm; }',
        '@media print {',
        '    .print-controls { display: none !important; }',
        '    body { font-size: 10pt; }',
        '    .section-title { margin-top: 14px; }',
        '    /* A4 report wrapper */',
        '    .report-wrapper { box-sizing: border-box; width: 210mm; min-height: 297mm; }',
        '    /* Repeating footer — fixed at bottom of every printed page */',
        '    .rpt-footer {',
        '        position: fixed; bottom: 0; left: 0; right: 0; width: 100%;',
        '        font-size: 8pt; color: #555; border-top: 1px solid #ccc;',
        '        padding: 4mm 16px 2mm; background: #fff; z-index: 9999;',
        '        display: flex; justify-content: space-between; align-items: flex-start;',
        '    }',
        '    .rpt-footer .conf {',
        '        color: #c0392b; font-weight: 600; font-style: normal; text-align: center; flex: 1;',
        '    }',
        '    /* Page-break rules — no mid-row or mid-section cuts */',
        '    .section-card, .participants-summary, .examiner-table,',
        '    .paths-breakdown, .student-list-table { page-break-inside: avoid; }',
        '    .section-card + .section-card { page-break-before: auto; }',
        '    .student-list-section { page-break-before: auto; }',
        '    h2, h3 { page-break-after: avoid; }',
        '    /* RTL & Arabic text */',
        '    [dir="rtl"], .arabic-text { direction: rtl; text-align: right; }',
        '    td.arc { white-space: nowrap; }',
        '}'
        ].join('\n');
    }

    /* ── HTML builders ────────────────────────────────────────────────────── */

    function buildHeader(meta, generatedAt, reportId) {
        var statusColor = STATUS_CSS[meta.sessionStatus] || '#646e78';
        return [
            '<div class="print-controls">',
            '  <button class="btn-print" onclick="window.print()">\uD83D\uDDA8\uFE0F Print / Save as PDF</button>',
            '  <button class="btn-close-w" onclick="window.close()">\u2715 Close</button>',
            '  <span style="font-size:8pt;color:#555">Use your browser\'s <b>Print &rarr; Save as PDF</b> for the best Arabic rendering.</span>',
            '</div>',
            '<div class="rpt-header">',
            '  <div class="rpt-header-top">',
            '    <div class="rpt-logo-area">',
            '      <div class="rpt-logo-box">',
            '        <span class="logo-main">OSCE</span>',
            '        <span class="logo-sub">SYSTEM</span>',
            '      </div>',
            '      <div class="rpt-title-area">',
            '        <h1>OSCE Session Report</h1>',
            '        <p>Objective Structured Clinical Examination &mdash; Confidential</p>',
            '      </div>',
            '    </div>',
            '    <div class="rpt-meta">',
            '      <div>Generated: <strong>' + esc(generatedAt) + '</strong></div>',
            '      <div>Report ID: <strong>' + esc(reportId) + '</strong></div>',
            '      <div style="margin-top:4px;padding:2px 8px;border-radius:3px;background:' + statusColor + ';color:#fff;display:inline-block;font-size:7.5pt;">',
            '        ' + esc(capitalize(meta.sessionStatus)),
            '      </div>',
            '    </div>',
            '  </div>',
            '</div>',
        ].join('\n');
    }

    function buildSection1(meta, reportId) {
        var statusColor = STATUS_CSS[meta.sessionStatus] || '#646e78';

        function card(label, value) {
            var ar = hasArabic(value);
            return [
                '<div class="info-card">',
                '  <div class="card-label">' + esc(label) + '</div>',
                '  <div class="card-value"' + (ar ? ' style="direction:rtl;text-align:right;"' : '') + '>',
                '    ' + arabicCell(value || 'N/A'),
                '  </div>',
                '</div>',
            ].join('');
        }

        var row1 = [
            card('Exam Name',    meta.examName),
            card('Session Name', meta.sessionName),
            card('Session Date', fmtDate(meta.sessionDate)),
            '<div class="info-card status-card" style="background:' + statusColor + '">',
            '  <div class="card-label">Status</div>',
            '  <div class="card-value">' + esc(capitalize(meta.sessionStatus)) + '</div>',
            '</div>',
        ].join('');

        var row2 = '';
        if (meta.courseName || meta.department) {
            row2 = '<div class="cards-row">' + [
                card('Course',     meta.courseName || 'N/A'),
                card('Department', meta.department  || 'N/A'),
                card('Report ID',  reportId),
            ].join('') + '</div>';
        }

        return [
            '<div class="section-title">1.&nbsp; Session Overview</div>',
            '<div class="cards-row">' + row1 + '</div>',
            row2,
        ].join('\n');
    }

    function buildSection2(totals) {
        function card(label, value) {
            return [
                '<div class="info-card">',
                '  <div class="card-label">' + esc(label) + '</div>',
                '  <div class="card-value">' + esc(String(value)) + '</div>',
                '</div>',
            ].join('');
        }
        return [
            '<div class="section-title">2.&nbsp; Participants Summary</div>',
            '<div class="cards-row">',
            card('Total Students',   totals.students),
            card('Examiners',        totals.examiners),
            card('Total Stations',   totals.stations),
            card('Paths / Circuits', totals.paths),
            '</div>',
        ].join('\n');
    }

    function buildSection3(assignments, stationToPath, examinerById) {
        if (!assignments.length) {
            return [
                '<div class="section-title">3.&nbsp; Examiner Assignments</div>',
                '<p class="no-data">No examiner assignments have been recorded for this session.</p>',
            ].join('\n');
        }

        var sorted = assignments.slice().sort(function (a, b) {
            var pa = stationToPath[a.station_id] || '';
            var pb = stationToPath[b.station_id] || '';
            return pa.localeCompare(pb) || (a.station_number || 0) - (b.station_number || 0);
        });

        var rows = sorted.map(function (a) {
            var ex   = examinerById[a.examiner_id];
            var name = ex ? ex.full_name : (a.examiner_name || '\u2014');
            var path = stationToPath[a.station_id] ? 'Path ' + esc(stationToPath[a.station_id]) : '\u2014';
            var ar   = hasArabic(name);
            return [
                '<tr>',
                '<td class="' + (ar ? 'arc' : 'tl') + '">' + arabicCell(name) + '</td>',
                '<td class="tc">' + path + '</td>',
                '<td class="tl">' + esc(a.station_name || '\u2014') + '</td>',
                '<td class="tc">' + esc(a.station_number != null ? String(a.station_number) : '\u2014') + '</td>',
                '</tr>',
            ].join('');
        }).join('');

        return [
            '<div class="section-title">3.&nbsp; Examiner Assignments</div>',
            '<table>',
            '<thead><tr>',
            '<th class="tl">Examiner Name</th>',
            '<th>Path</th>',
            '<th class="tl">Station Name</th>',
            '<th>Stn #</th>',
            '</tr></thead>',
            '<tbody>' + rows + '</tbody>',
            '</table>',
        ].join('\n');
    }

    function buildSection5(paths) {
        var rows = [];
        paths.forEach(function (path) {
            var stations = (path.stations || []).slice().sort(function (a, b) {
                return (a.station_number || 0) - (b.station_number || 0);
            });
            (path.students || []).forEach(function (stu, idx) {
                var startStation = '\u2014';
                if (stations.length) {
                    var st = stations[idx % stations.length];
                    startStation = st ? ((st.station_number || (idx % stations.length + 1)) + '. ' + (st.name || '')) : '\u2014';
                }
                rows.push({
                    name:     stu.full_name      || '\u2014',
                    ar:       hasArabic(stu.full_name),
                    id:       stu.student_number || '\u2014',
                    numVal:   parseInt(stu.student_number) || 0,
                    path:     'Path ' + path.name,
                    start:    startStation,
                    status:   capitalize(stu.status || 'registered'),
                });
            });
        });

        rows.sort(function (a, b) { return a.numVal - b.numVal; });

        if (!rows.length) {
            return [
                '<div class="section-title">4.&nbsp; Student List</div>',
                '<p class="no-data">No students enrolled in this session.</p>',
            ].join('\n');
        }

        var tbody = rows.map(function (r) {
            return [
                '<tr>',
                '<td class="' + (r.ar ? 'arc' : 'tl') + '">' + arabicCell(r.name) + '</td>',
                '<td class="tc">' + esc(String(r.id)) + '</td>',
                '<td class="tc">' + esc(r.path) + '</td>',
                '<td class="tl">' + esc(r.start) + '</td>',
                '<td class="tc">' + esc(r.status) + '</td>',
                '</tr>',
            ].join('');
        }).join('');

        return [
            '<div class="section-title">4.&nbsp; Student List</div>',
            '<table>',
            '<thead><tr>',
            '<th class="tl">Full Name</th>',
            '<th>Student ID</th>',
            '<th>Assigned Path</th>',
            '<th class="tl">Starting Station</th>',
            '<th>Status</th>',
            '</tr></thead>',
            '<tbody>' + tbody + '</tbody>',
            '</table>',
        ].join('\n');
    }

    function buildFooter(generatedAt) {
        return [
            '<div class="rpt-footer">',
            '  <span>Generated by OSCE Management System</span>',
            '  <span class="conf">',
            '    CONFIDENTIAL &ndash; This report contains sensitive examination information.',
            '    Unauthorized distribution is strictly prohibited.',
            '  </span>',
            '  <span>' + esc(generatedAt) + '</span>',
            '</div>',
        ].join('\n');
    }

    /* ── main ─────────────────────────────────────────────────────────────── */
    async function generateSessionReport(sessionId, meta) {
        var btn       = document.getElementById('btn-download-report');
        var origLabel = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled  = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Building Report\u2026';
        }

        // Decode Django |escapejs sequences in meta strings
        meta.sessionName = unescapeJs(meta.sessionName || '');
        meta.examName    = unescapeJs(meta.examName    || '');
        meta.courseName  = unescapeJs(meta.courseName  || '');
        meta.department  = unescapeJs(meta.department  || '');

        try {
            var results = await Promise.all([
                fetchJSON('/api/creator/sessions/' + sessionId + '/paths'),
                fetchJSON('/api/creator/sessions/' + sessionId + '/assignments'),
                fetchJSON('/api/creator/examiners'),
            ]);
            var paths       = results[0];
            var assignments = results[1];
            var examiners   = results[2];

            /* derived lookups */
            var examinerById = {};
            examiners.forEach(function (e) { examinerById[e.id] = e; });

            var assignByStation = {};
            assignments.forEach(function (a) {
                assignByStation[a.station_id] = {
                    station_id:    a.station_id,
                    examiner_id:   a.examiner_id,
                    examiner_name: a.examiner_name,
                    station_name:  a.station_name,
                    station_number: a.station_number,
                    examiner:      examinerById[a.examiner_id] || null,
                };
            });

            var stationToPath = {};
            paths.forEach(function (p) {
                (p.stations || []).forEach(function (s) { stationToPath[s.id] = p.name; });
            });

            /* totals */
            var totalPaths    = paths.length;
            var totalStations = paths.reduce(function (n, p) { return n + (p.stations || []).length; }, 0);
            var totalStudents = paths.reduce(function (n, p) { return n + (p.students || []).length; }, 0);
            var assignedIds   = new Set(assignments.map(function (a) { return a.examiner_id; }).filter(Boolean));
            var totalExaminers = assignedIds.size;

            var generatedAt = fmtNow();
            var reportId    = genReportId(sessionId);
            var title       = 'Session Report \u2013 ' + (meta.sessionName || sessionId);

            /* ── assemble full HTML document ─────────────────────────────── */
            var html = [
                '<!DOCTYPE html>',
                '<html lang="en">',
                '<head>',
                '  <meta charset="UTF-8">',
                '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                '  <title>' + esc(title) + '</title>',
                '  <style>' + buildCSS() + '</style>',
                '</head>',
                '<body>',
                buildHeader(meta, generatedAt, reportId),
                '<div class="report-wrapper">',
                buildSection1(meta, reportId),
                buildSection2({ students: totalStudents, examiners: totalExaminers,
                                stations: totalStations, paths: totalPaths }),
                buildSection3(assignments, stationToPath, examinerById),
                buildSection5(paths),
                '</div>',
                buildFooter(generatedAt),
                '<script>',
                '  window.addEventListener("load", function () {',
                '    setTimeout(function () { window.print(); }, 700);',
                '  });',
                '<\/script>',
                '</body>',
                '</html>',
            ].join('\n');

            /* open in a new window — browser handles all text layout incl. Arabic */
            var win = window.open('', '_blank', 'width=960,height=720,scrollbars=yes');
            if (!win) {
                alert('Pop-up blocked.\nPlease allow pop-ups for this site and click the button again.');
                return;
            }
            win.document.open();
            win.document.write(html);
            win.document.close();
            win.document.title = title;

        } catch (err) {
            console.error('[session-report] Error:', err);
            alert('Failed to generate session report:\n' + err.message);
        } finally {
            if (btn) {
                btn.disabled  = false;
                btn.innerHTML = origLabel;
            }
        }
    }

    global.generateSessionReport = generateSessionReport;

    /* ═══════════════════════════════════════════════════════════════════════
       Student Path Distribution Report
       — 3 paths side-by-side per A4 page, 12 pt text, native Arabic
       ═══════════════════════════════════════════════════════════════════════ */

    function buildStudentPathsCSS() {
        /* Extend the shared session-report CSS with 3-column path layout rules */
        return buildCSS() + '\n' + [
        '/* ── 3-column path layout ──────────────────────────────────── */',
        '.spl-title { font-size: 16pt; font-weight: 700; margin: 0; color: var(--white); }',

        '/* A4 page: 3 paths sit side-by-side as columns; page breaks after each group */',
        '.paths-page {',
        '    display: table; border-collapse: collapse;',
        '    width: 100%; table-layout: fixed;',
        '    page-break-after: always; break-after: page;',
        '}',
        '.paths-page.last-page { page-break-after: auto; break-after: auto; }',

        '/* Wrapper row inside the table */',
        '.paths-row {',
        '    display: table-row;',
        '}',

        '.path-col {',
        '    display: table-cell;',
        '    width: 33.333%;',
        '    vertical-align: top;',
        '    border: 1px solid var(--mgray);',
        '    border-right-width: 0;',
        '}',
        '.path-col:last-child { border-right-width: 1px; }',
        '.path-col-placeholder { display: table-cell; width: 33.333%; }',

        '.path-col-header {',
        '    background: var(--navy); color: var(--white);',
        '    text-align: center; font-weight: 700; font-size: 11pt;',
        '    padding: 8px 6px;',
        '    border-bottom: 3px solid var(--accent);',
        '    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;',
        '    page-break-after: avoid; break-after: avoid;',
        '}',
        '.path-col-sub {',
        '    background: var(--navy2); color: rgba(255,255,255,.85);',
        '    font-size: 7pt; text-align: center;',
        '    padding: 3px 6px; border-bottom: 1px solid #1a3a5c;',
        '    page-break-after: avoid; break-after: avoid;',
        '}',

        '/* One student per row — never cut a row across a page */',
        '.student-row {',
        '    display: block;',
        '    padding: 5px 9px;',
        '    border-bottom: 1px solid var(--mgray);',
        '    font-size: 11pt; line-height: 1.4;',
        '    text-align: center; word-break: break-word;',
        '    page-break-inside: avoid; break-inside: avoid;',
        '}',
        '.student-row:nth-child(even) { background: var(--lgray); }',
        '.student-row.ar {',
        '    font-family: "Amiri","Noto Naskh Arabic","Traditional Arabic",',
        '                 "Arabic Typesetting","Simplified Arabic",serif;',
        '    direction: rtl; text-align: center;',
        '}',
        '.path-empty {',
        '    padding: 10px; text-align: center;',
        '    color: var(--dgray); font-style: italic; font-size: 9pt;',
        '}',
        ].join('\n');
    }

    async function generateStudentPathsReport(sessionId, meta) {
        var btn     = document.getElementById('pdfDownloadBtn');
        var content = document.getElementById('pdfBtnContent');
        var spinner = document.getElementById('pdfBtnSpinner');
        var origLabel = content ? content.innerHTML : '';

        if (btn)     { btn.style.pointerEvents = 'none'; }
        if (content) { content.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Generating\u2026'; }
        if (spinner) { spinner.classList.remove('d-none'); }

        try {
            var paths = await fetchJSON('/api/creator/sessions/' + sessionId + '/paths');

            var generatedAt  = fmtNow();
            var sessionName  = unescapeJs(meta.sessionName || String(sessionId));
            var title        = 'Student Path Assignments \u2013 ' + sessionName;

            /* ── Build path column markup ──────────────────────────────── */
            function buildPathColumn(path) {
                var students = path.students || [];
                var count    = students.length;
                var hdr = [
                    '<div class="path-col-header">Path ' + esc(path.name) + '</div>',
                    '<div class="path-col-sub">' + count + ' student' +
                        (count !== 1 ? 's' : '') + '</div>',
                ].join('');

                if (!count) {
                    return hdr + '<div class="path-empty">No students assigned</div>';
                }
                /* One student per row — centered, no numbering */
                var rows = students.map(function (stu, idx) {
                    var name = stu.full_name || '\u2014';
                    var ar   = hasArabic(name);
                    return '<div class="student-row' + (ar ? ' ar' : '') + '">' +
                           (ar ? arabicCell(name) : esc(name)) + '</div>';
                }).join('');
                return hdr + rows;
            }

            /* ── Group paths into chunks of 3 (table-cell columns) ─────── */
            var PER_PAGE  = 3;
            var pageGroups = [];
            for (var i = 0; i < paths.length; i += PER_PAGE) {
                pageGroups.push(paths.slice(i, i + PER_PAGE));
            }
            if (!pageGroups.length) { pageGroups.push([]); }

            var pagesHtml = pageGroups.map(function (group, pageIdx) {
                var isLast = pageIdx === pageGroups.length - 1;
                var cols;
                if (!group.length) {
                    cols = '<div class="path-col"><div class="path-empty">No paths defined.</div></div>';
                } else {
                    cols = group.map(function (p) {
                        return '<div class="path-col">' + buildPathColumn(p) + '</div>';
                    }).join('');
                    /* Pad with invisible placeholder cells to keep table balanced */
                    for (var k = group.length; k < PER_PAGE; k++) {
                        cols += '<div class="path-col-placeholder"></div>';
                    }
                }
                return '<div class="paths-page' + (isLast ? ' last-page' : '') + '"><div class="paths-row">' + cols + '</div></div>';
            }).join('\n');

            /* ── Page header (same design as session report) ───────────── */
            var reportHeader = [
                '<div class="rpt-header">',
                '  <!-- Student Path Assignments Report — no UI chrome; printed via iframe -->',

                '  <div class="rpt-header-top">',
                '    <div class="rpt-logo-area">',
                '      <div class="rpt-logo-box">',
                '        <span class="logo-main">OSCE</span>',
                '        <span class="logo-sub">SYSTEM</span>',
                '      </div>',
                '      <div class="rpt-title-area">',
                '        <h1 class="spl-title">Student Path Assignments</h1>',
                '        <p>' + esc(sessionName) + '</p>',
                '      </div>',
                '    </div>',
                '    <div class="rpt-meta">',
                '      <div>Generated: <strong>' + esc(generatedAt) + '</strong></div>',
                '      <div>Total Paths: <strong>' + esc(String(paths.length)) + '</strong></div>',
                '    </div>',
                '  </div>',
                '</div>',
            ].join('\n');

            var footer = [
                '<div class="rpt-footer">',
                '  <span>Generated by OSCE Management System</span>',
                '  <span class="conf">CONFIDENTIAL &ndash; Unauthorized distribution is strictly prohibited.</span>',
                '  <span>' + esc(generatedAt) + '</span>',
                '</div>',
            ].join('\n');

            var html = [
                '<!DOCTYPE html>',
                '<html lang="en">',
                '<head>',
                '  <meta charset="UTF-8">',
                '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                '  <title>' + esc(title) + '</title>',
                '  <style>' + buildStudentPathsCSS() + '</style>',
                '</head>',
                '<body>',
                reportHeader,
                '<div class="report-wrapper" style="padding-top:14px;">',
                pagesHtml,
                '</div>',
                footer,
                '</body>',
                '</html>',
            ].join('\n');

            /* ── Print via hidden iframe (no new tab opens) ──────────── */
            var iframe = document.createElement('iframe');
            iframe.setAttribute('aria-hidden', 'true');
            /* Full-size but invisible so fonts and CSS render correctly */
            iframe.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
                                   'z-index:-9999;border:none;opacity:0;pointer-events:none;';
            document.body.appendChild(iframe);

            var idoc = iframe.contentDocument || iframe.contentWindow.document;
            idoc.open('text/html', 'replace');
            idoc.write(html);
            idoc.close();

            /* Give fonts/images time to load, then open the Save-as-PDF print dialog */
            setTimeout(function () {
                try { iframe.contentWindow.focus(); } catch (e) {}
                iframe.contentWindow.print();
                /* Clean up the iframe:  on focus-return (user closed dialog) or after 60 s */
                function cleanup() {
                    setTimeout(function () {
                        if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
                    }, 500);
                }
                window.addEventListener('focus', cleanup, { once: true });
                setTimeout(cleanup, 60000);
            }, 800);

        } catch (err) {
            console.error('[student-paths] Error:', err);
            alert('Failed to generate student path list:\n' + err.message);
        } finally {
            if (btn)     { btn.style.pointerEvents = ''; }
            if (content) { content.innerHTML = origLabel; }
            if (spinner) { spinner.classList.add('d-none'); }
        }
    }

    global.generateStudentPathsReport = generateStudentPathsReport;

})(window);
