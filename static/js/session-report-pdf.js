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

    function buildSection4(paths, assignByStation) {
        if (!paths.length) {
            return [
                '<div class="section-title">4.&nbsp; Paths &amp; Stations Breakdown</div>',
                '<p class="no-data">No paths defined for this session.</p>',
            ].join('\n');
        }

        var blocks = paths.map(function (path) {
            var stations = path.stations || [];
            var rotMin   = path.rotation_minutes ? (path.rotation_minutes + ' min/station') : '\u2014';
            var hdr      = [
                '<div class="path-header">',
                'Path ' + esc(path.name) + ' &nbsp;&middot;&nbsp; ',
                stations.length + ' station(s) &nbsp;&middot;&nbsp; ',
                (path.student_count || 0) + ' student(s) &nbsp;&middot;&nbsp; ',
                esc(rotMin),
                '</div>',
            ].join('');

            if (!stations.length) {
                return hdr + '<p class="no-data" style="padding-left:8px">No stations configured for this path.</p>';
            }

            var rows = stations.map(function (s, idx) {
                var asgn  = assignByStation[s.id];
                var durMin = s.duration_minutes || path.rotation_minutes;
                var name   = asgn
                    ? (asgn.examiner ? asgn.examiner.full_name : (asgn.examiner_name || '\u2014'))
                    : 'Unassigned';
                var ar = hasArabic(name);
                return [
                    '<tr>',
                    '<td class="tc">Path ' + esc(path.name) + '</td>',
                    '<td class="tc">' + esc(s.station_number != null ? s.station_number : idx + 1) + '</td>',
                    '<td class="tl">' + esc(s.name || '\u2014') + '</td>',
                    '<td class="tc">' + (durMin ? esc(String(durMin)) + ' min' : '\u2014') + '</td>',
                    '<td class="' + (ar ? 'arc' : 'tl') + '">' + arabicCell(name) + '</td>',
                    '</tr>',
                ].join('');
            }).join('');

            return [
                hdr,
                '<table>',
                '<thead><tr>',
                '<th>Path</th><th>Stn #</th>',
                '<th class="tl">Station Name</th>',
                '<th>Duration</th>',
                '<th class="tl">Assigned Examiner</th>',
                '</tr></thead>',
                '<tbody>' + rows + '</tbody>',
                '</table>',
            ].join('\n');
        }).join('');

        return '<div class="section-title">4.&nbsp; Paths &amp; Stations Breakdown</div>\n' + blocks;
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
                '<div class="section-title">5.&nbsp; Student List</div>',
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
            '<div class="section-title">5.&nbsp; Student List</div>',
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
                buildSection4(paths, assignByStation),
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

})(window);
