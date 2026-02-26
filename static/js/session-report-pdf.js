/**
 * session-report-pdf.js
 * ─────────────────────────────────────────────────────────────────────────────
 * OSCE Session Report PDF Generator
 * Uses jsPDF (UMD) + jsPDF-AutoTable loaded from CDN.
 *
 * Entry point:  window.generateSessionReport(sessionId, meta)
 *   meta = { sessionName, sessionDate, sessionStatus, examName,
 *             courseName, department }
 *
 * Data sources (all existing REST endpoints, no backend changes):
 *   GET /api/creator/sessions/<id>/paths         → paths + stations + students
 *   GET /api/creator/sessions/<id>/assignments   → examiner ↔ station map
 *   GET /api/creator/examiners                   → examiner details
 * ─────────────────────────────────────────────────────────────────────────────
 */
(function (global) {
    'use strict';

    /* ── Colour palette ───────────────────────────────────────────────────── */
    const C = {
        navy:    [26,  58,  92],
        navy2:   [38,  80, 128],
        navyLt:  [60, 110, 170],
        white:   [255, 255, 255],
        lgray:   [245, 247, 250],
        mgray:   [200, 210, 220],
        dgray:   [100, 110, 120],
        accent:  [41,  182, 246],
        green:   [22,  155,  98],
        amber:   [217, 119,   6],
        red:     [192,  57,  43],
    };

    const STATUS_COLOR = {
        scheduled:   C.navyLt,
        in_progress: C.green,
        completed:   [41, 128, 185],
        archived:    C.dgray,
        cancelled:   C.red,
    };

    /* ── General helpers ──────────────────────────────────────────────────── */
    function fmtDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            const d = new Date(dateStr);
            if (isNaN(d)) return dateStr;
            return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
        } catch (_) { return dateStr; }
    }

    function fmtNow() {
        return new Date().toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function capitalize(str) {
        if (!str) return '';
        return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    function genReportId(sessionId) {
        const rand = Math.random().toString(36).substring(2, 6).toUpperCase();
        return `RPT-${rand}-${(sessionId || 'XXXX').substring(0, 8).toUpperCase()}`;
    }

    function safeFilename(str) {
        return (str || 'session').replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_');
    }

    /* ─────────────────────────────────────────────────────────────────────── */
    /*  ARABIC TEXT SUPPORT  (complete rewrite)                               */
    /*                                                                         */
    /*  Root causes of the garbled output that was seen:                       */
    /*    1. jsPDF renders glyphs in the order it receives them.  Arabic is a  */
    /*       right-to-left script, so the logical (Unicode) string must be     */
    /*       converted into VISUAL left-to-right order before being handed to  */
    /*       jsPDF.                                                             */
    /*    2. Arabic letters have 4 contextual shapes (isolated / initial /     */
    /*       medial / final).  The plain Unicode codepoints are the "isolated" */
    /*       form.  Without shaping the characters look disconnected.          */
    /*    3. Mixed Arabic + Latin names need each segment handled separately.  */
    /*                                                                         */
    /*  Strategy used here:                                                    */
    /*    • Split the string into Arabic and non-Arabic segments.              */
    /*    • Shape every Arabic segment using the Arabic Presentation Forms B   */
    /*      table (U+FE70–U+FEFF) — the same block the old code used, but     */
    /*      with corrected connectivity logic.                                 */
    /*    • Reverse each Arabic segment's character array (visual order).      */
    /*    • Reverse the ORDER of all segments (RTL paragraph direction).       */
    /*    • Rejoin into a single string that jsPDF can render left-to-right.   */
    /* ─────────────────────────────────────────────────────────────────────── */

    /** Decode \uXXXX escape sequences left by Django's |escapejs filter. */
    function unescapeJs(str) {
        if (!str) return str;
        return str.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) =>
            String.fromCharCode(parseInt(hex, 16))
        );
    }

    /** True if str contains any Arabic-script codepoint. */
    function hasArabic(str) {
        return /[\u0600-\u06FF\uFE70-\uFEFF]/.test(str);
    }

    /* ── Arabic letter shape tables ─────────────────────────────────────── */
    /*  Each entry: [isolated, final, initial, medial]                        */
    const ARABIC_SHAPES = {
        '\u0621': ['\uFE80','\uFE80','\uFE80','\uFE80'],
        '\u0622': ['\uFE81','\uFE82','\uFE81','\uFE82'],
        '\u0623': ['\uFE83','\uFE84','\uFE83','\uFE84'],
        '\u0624': ['\uFE85','\uFE86','\uFE85','\uFE86'],
        '\u0625': ['\uFE87','\uFE88','\uFE87','\uFE88'],
        '\u0626': ['\uFE89','\uFE8A','\uFE8B','\uFE8C'],
        '\u0627': ['\uFE8D','\uFE8E','\uFE8D','\uFE8E'],
        '\u0628': ['\uFE8F','\uFE90','\uFE91','\uFE92'],
        '\u0629': ['\uFE93','\uFE94','\uFE93','\uFE94'],
        '\u062A': ['\uFE95','\uFE96','\uFE97','\uFE98'],
        '\u062B': ['\uFE99','\uFE9A','\uFE9B','\uFE9C'],
        '\u062C': ['\uFE9D','\uFE9E','\uFE9F','\uFEA0'],
        '\u062D': ['\uFEA1','\uFEA2','\uFEA3','\uFEA4'],
        '\u062E': ['\uFEA5','\uFEA6','\uFEA7','\uFEA8'],
        '\u062F': ['\uFEA9','\uFEAA','\uFEA9','\uFEAA'],
        '\u0630': ['\uFEAB','\uFEAC','\uFEAB','\uFEAC'],
        '\u0631': ['\uFEAD','\uFEAE','\uFEAD','\uFEAE'],
        '\u0632': ['\uFEAF','\uFEB0','\uFEAF','\uFEB0'],
        '\u0633': ['\uFEB1','\uFEB2','\uFEB3','\uFEB4'],
        '\u0634': ['\uFEB5','\uFEB6','\uFEB7','\uFEB8'],
        '\u0635': ['\uFEB9','\uFEBA','\uFEBB','\uFEBC'],
        '\u0636': ['\uFEBD','\uFEBE','\uFEBF','\uFEC0'],
        '\u0637': ['\uFEC1','\uFEC2','\uFEC3','\uFEC4'],
        '\u0638': ['\uFEC5','\uFEC6','\uFEC7','\uFEC8'],
        '\u0639': ['\uFEC9','\uFECA','\uFECB','\uFECC'],
        '\u063A': ['\uFECD','\uFECE','\uFECF','\uFED0'],
        '\u0641': ['\uFED1','\uFED2','\uFED3','\uFED4'],
        '\u0642': ['\uFED5','\uFED6','\uFED7','\uFED8'],
        '\u0643': ['\uFED9','\uFEDA','\uFEDB','\uFEDC'],
        '\u0644': ['\uFEDD','\uFEDE','\uFEDF','\uFEE0'],
        '\u0645': ['\uFEE1','\uFEE2','\uFEE3','\uFEE4'],
        '\u0646': ['\uFEE5','\uFEE6','\uFEE7','\uFEE8'],
        '\u0647': ['\uFEE9','\uFEEA','\uFEEB','\uFEEC'],
        '\u0648': ['\uFEED','\uFEEE','\uFEED','\uFEEE'],
        '\u0649': ['\uFEEF','\uFEF0','\uFEEF','\uFEF0'],
        '\u064A': ['\uFEF1','\uFEF2','\uFEF3','\uFEF4'],
    };

    /**
     * Right-joining-only letters: they accept a connection from the RIGHT
     * (previous letter) but do NOT connect to the LEFT (next letter).
     * These have only isolated and final forms.
     */
    const RIGHT_ONLY = new Set([
        '\u0621','\u0622','\u0623','\u0624','\u0625',
        '\u0627','\u0629','\u062F','\u0630','\u0631',
        '\u0632','\u0648','\u0649',
    ]);

    /** Lam + Alef mandatory ligatures → [isolated-lig, final-lig] */
    const LAM_ALEF_LIGS = {
        '\u0622': ['\uFEF5', '\uFEF6'],
        '\u0623': ['\uFEF7', '\uFEF8'],
        '\u0625': ['\uFEF9', '\uFEFA'],
        '\u0627': ['\uFEFB', '\uFEFC'],
    };

    function isArabicChar(ch) {
        return ARABIC_SHAPES.hasOwnProperty(ch);
    }

    function isDualJoining(ch) {
        return isArabicChar(ch) && !RIGHT_ONLY.has(ch);
    }

    /**
     * Shape and visually reverse a single Arabic word.
     *
     * Input  : logical Unicode string  (e.g. "محمد")
     * Output : visually-ordered presentation-form string ready for jsPDF
     *
     * Key insight: Arabic text in Unicode is stored in LOGICAL order
     * (right-to-left reading order). jsPDF paints characters left-to-right
     * in the order it receives them. So we must:
     *   1. Resolve each letter's contextual shape (isolated/initial/medial/final)
     *   2. Reverse the array so the FIRST letter in reading order ends up
     *      on the RIGHT side when jsPDF paints left-to-right.
     */
    function shapeArabicWord(word) {
        if (!word) return '';

        // ── Strip tashkeel (diacritics) for connectivity analysis only ──────
        const clean = word.replace(/[\u064B-\u065F\u0670\u0640]/g, '');
        const chars = [...clean];
        const n = chars.length;
        if (n === 0) return '';

        // ── Step 1: Lam-Alef ligature substitution ──────────────────────────
        // Build a token list; Lam+Alef pairs → single ligature token
        const tokens = [];  // { glyph: string, rightOnly: boolean }
        for (let i = 0; i < n; i++) {
            if (chars[i] === '\u0644' && i + 1 < n && LAM_ALEF_LIGS[chars[i + 1]]) {
                // Lam-Alef ligature — right-joining only (like Alef)
                tokens.push({ type: 'lamalef', alef: chars[i + 1] });
                i++;
            } else {
                tokens.push({ type: 'char', ch: chars[i] });
            }
        }

        // ── Step 2: Determine connectivity and pick glyph form ──────────────
        const glyphs = [];

        for (let i = 0; i < tokens.length; i++) {
            const tok = tokens[i];

            if (tok.type === 'lamalef') {
                // Connects on the right if the PREVIOUS dual-joining token exists
                const prevIsDual = (i > 0) && tokens[i - 1].type === 'char' && isDualJoining(tokens[i - 1].ch);
                const lig = LAM_ALEF_LIGS[tok.alef];
                glyphs.push(prevIsDual ? lig[1] : lig[0]);  // final : isolated
                continue;
            }

            const ch = tok.ch;
            const forms = ARABIC_SHAPES[ch];

            if (!forms) {
                // Non-Arabic character inside an Arabic word (e.g. digit) — pass through
                glyphs.push(ch);
                continue;
            }

            // Does the PREVIOUS token connect to us from the right?
            let connFromRight = false;
            if (i > 0) {
                const prev = tokens[i - 1];
                if (prev.type === 'lamalef') {
                    // Lam-Alef is right-joining only; its left side does NOT connect
                    connFromRight = false;
                } else {
                    connFromRight = isDualJoining(prev.ch);
                }
            }

            // Does THIS letter connect to the NEXT token on the left?
            let connToLeft = false;
            if (isDualJoining(ch) && i + 1 < tokens.length) {
                const next = tokens[i + 1];
                // We can connect left if next is any Arabic letter or a Lam-Alef lig
                connToLeft = (next.type === 'lamalef') || isArabicChar(next.ch);
            }

            // Form index: 0=isolated  1=final  2=initial  3=medial
            let form;
            if      (connFromRight && connToLeft) form = 3; // medial
            else if (connFromRight)               form = 1; // final
            else if (connToLeft)                  form = 2; // initial
            else                                  form = 0; // isolated

            glyphs.push(forms[form]);
        }

        // ── Step 3: Reverse for visual left-to-right rendering ───────────────
        return glyphs.reverse().join('');
    }

    /**
     * Process a full text string that may contain Arabic, Latin, digits, etc.
     *
     * Algorithm:
     *   1. Tokenise into alternating Arabic-script and non-Arabic segments.
     *   2. Shape each Arabic segment word-by-word.
     *   3. Reverse the ORDER of ALL segments (paragraph-level RTL).
     *   4. Within each reversed Arabic segment also reverse the word order.
     *   5. Rejoin and return.
     *
     * Example  : "محمد جمال"  →  shaped("جمال") + " " + shaped("محمد")
     * Example  : "محمد Smith" →  "Smith " + shaped("محمد")
     */
    function processArabicText(text) {
        if (!text) return text;
        const unescaped = unescapeJs(text);
        if (!hasArabic(unescaped)) return unescaped;

        // Split into segments: Arabic runs vs non-Arabic runs
        // Regex: one or more Arabic chars (including spaces within Arabic context)
        const segments = [];
        const RE = /([\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+)/g;
        let last = 0;
        let m;
        while ((m = RE.exec(unescaped)) !== null) {
            if (m.index > last) {
                segments.push({ arabic: false, text: unescaped.slice(last, m.index) });
            }
            segments.push({ arabic: true, text: m[0] });
            last = m.index + m[0].length;
        }
        if (last < unescaped.length) {
            segments.push({ arabic: false, text: unescaped.slice(last) });
        }

        // Shape Arabic segments (shape word-by-word, preserving spaces)
        const shaped = segments.map(seg => {
            if (!seg.arabic) return seg.text;
            // Split on spaces, shape each word, reverse word order within segment
            const words = seg.text.split(' ');
            return words
                .map(w => shapeArabicWord(w))
                .reverse()
                .join(' ');
        });

        // Reverse segment order for RTL paragraph direction
        return shaped.reverse().join('');
    }

    /**
     * Fetch Amiri-Regular.ttf and register it with the jsPDF document.
     * Returns true on success.
     */
    async function loadArabicFont(doc) {
        try {
            const resp = await fetch('/static/js/fonts/amiri-regular.ttf');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const buf   = await resp.arrayBuffer();
            const bytes = new Uint8Array(buf);

            // Convert bytes → base64 in chunks to avoid call-stack overflow
            let binary = '';
            const CHUNK = 8192;
            for (let i = 0; i < bytes.length; i += CHUNK) {
                binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + CHUNK, bytes.length)));
            }

            doc.addFileToVFS('amiri-regular.ttf', btoa(binary));
            doc.addFont('amiri-regular.ttf', 'Amiri', 'normal');
            return true;
        } catch (e) {
            console.warn('[PDF] Arabic font unavailable — Arabic names may not render correctly:', e.message);
            return false;
        }
    }

    /* ─────────────────────────────────────────────────────────────────────── */
    /*  PDF BUILDING BLOCKS                                                    */
    /* ─────────────────────────────────────────────────────────────────────── */

    function paintPageHeader(doc, meta, generatedAt, reportId, pageNum, totalPages) {
        const pw = doc.internal.pageSize.getWidth();
        const BAR_H = 30;

        doc.setFillColor(...C.navy);
        doc.rect(0, 0, pw, BAR_H, 'F');

        doc.setFillColor(...C.accent);
        doc.rect(0, BAR_H - 1.2, pw, 1.2, 'F');

        // Logo placeholder
        doc.setFillColor(255, 255, 255);
        doc.setGState(doc.GState({ opacity: 0.12 }));
        doc.roundedRect(11, 5, 24, 20, 3, 3, 'F');
        doc.setGState(doc.GState({ opacity: 1 }));

        doc.setTextColor(...C.white);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(8.5);
        doc.text('OSCE', 23, 14, { align: 'center' });
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(6);
        doc.text('SYSTEM', 23, 19, { align: 'center' });

        // Title
        doc.setTextColor(...C.white);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(15);
        doc.text('OSCE Session Report', 40, 14);

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7.5);
        doc.setTextColor(180, 210, 240);
        doc.text('Objective Structured Clinical Examination — Confidential', 40, 21);

        // Right: generated date + page
        doc.setFontSize(7);
        doc.setTextColor(200, 225, 245);
        doc.text(`Generated : ${generatedAt}`, pw - 11, 13, { align: 'right' });
        doc.text(`Page ${pageNum} of ${totalPages}`, pw - 11, 20, { align: 'right' });
    }

    function paintPageFooter(doc, pageNum, totalPages) {
        const pw = doc.internal.pageSize.getWidth();
        const ph = doc.internal.pageSize.getHeight();
        const y  = ph - 14;

        doc.setFillColor(...C.lgray);
        doc.rect(0, y - 1, pw, 15, 'F');

        doc.setDrawColor(...C.mgray);
        doc.setLineWidth(0.3);
        doc.line(11, y - 1, pw - 11, y - 1);

        doc.setFontSize(6.5);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(...C.dgray);
        doc.text(
            'CONFIDENTIAL – This report contains sensitive examination information. Unauthorized distribution is strictly prohibited.',
            pw / 2, y + 3.5, { align: 'center' }
        );

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(6.5);
        doc.text('Generated by OSCE Management System', 11, y + 9);

        doc.setFont('helvetica', 'bold');
        doc.text(`Page ${pageNum} / ${totalPages}`, pw - 11, y + 9, { align: 'right' });

        const sigX = pw / 2;
        doc.setDrawColor(...C.mgray);
        doc.line(sigX - 35, y + 9, sigX + 35, y + 9);
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(6);
        doc.text('Authorized Signature', sigX, y + 8.5, { align: 'center' });
    }

    function drawSectionTitle(doc, y, number, title) {
        const pw     = doc.internal.pageSize.getWidth();
        const MARGIN = 12;
        doc.setFillColor(...C.navy);
        doc.rect(MARGIN, y, pw - MARGIN * 2, 8, 'F');
        doc.setFillColor(...C.accent);
        doc.rect(MARGIN, y, 3, 8, 'F');
        doc.setTextColor(...C.white);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9.5);
        doc.text(`${number}.  ${title}`, MARGIN + 7, y + 5.5);
        return y + 12;
    }

    /**
     * Draw a single info card.
     * Text is auto-shrunk and wrapped to stay INSIDE the card boundaries.
     */
    function drawInfoCard(doc, x, y, w, h, label, value, bgColor) {
        const bg = bgColor || C.lgray;
        doc.setFillColor(...bg);
        doc.roundedRect(x, y, w, h, 2, 2, 'F');
        doc.setDrawColor(...C.mgray);
        doc.setLineWidth(0.25);
        doc.roundedRect(x, y, w, h, 2, 2, 'S');

        // Label
        doc.setFontSize(6.5);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(...C.dgray);
        doc.text(String(label), x + 3, y + 5);

        // Value — shrink until it fits within 2 lines
        const valStr = String(value == null ? 'N/A' : value);
        const maxW   = w - 6;  // 3 mm padding each side
        const maxH   = h - 9;  // space below label baseline

        doc.setFont('helvetica', 'bold');
        doc.setTextColor(...C.navy);

        let fontSize = 9.5;
        let lines;
        while (fontSize >= 5.5) {
            doc.setFontSize(fontSize);
            lines = doc.splitTextToSize(valStr, maxW);
            if (lines.length <= 2) break;
            fontSize -= 0.5;
        }
        // Safety: hard-truncate to 2 lines with ellipsis on the last if needed
        if (lines.length > 2) {
            lines = lines.slice(0, 2);
            if (lines[1].length > 3) {
                lines[1] = lines[1].substring(0, lines[1].length - 3) + '…';
            }
        }

        const lineH = fontSize * 0.45 + 1;
        lines.forEach((line, i) => {
            const lineY = y + 12 + i * lineH;
            if (lineY + lineH <= y + h - 1) {   // clip to card bottom
                doc.text(line, x + 3, lineY);
            }
        });
    }

    function checkPageBreak(doc, y, threshold) {
        const ph = doc.internal.pageSize.getHeight();
        if (y >= (threshold || ph - 30)) {
            doc.addPage();
            return 36;
        }
        return y;
    }

    /* ─────────────────────────────────────────────────────────────────────── */
    /*  MAIN GENERATOR                                                         */
    /* ─────────────────────────────────────────────────────────────────────── */
    async function generateSessionReport(sessionId, meta) {
        if (!window.jspdf || !window.jspdf.jsPDF) {
            alert('PDF library failed to load. Please check your internet connection and try again.');
            return;
        }

        // Decode \uXXXX escape sequences in all meta strings
        meta.sessionName = unescapeJs(meta.sessionName || '');
        meta.examName    = unescapeJs(meta.examName    || '');
        meta.courseName  = unescapeJs(meta.courseName  || '');
        meta.department  = unescapeJs(meta.department  || '');

        const btn = document.getElementById('btn-download-report');
        const originalLabel = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled  = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Building PDF…';
        }

        try {
            /* ── Fetch data ─────────────────────────────────────────────── */
            const [pathsRes, assignmentsRes, examinersRes] = await Promise.all([
                fetch(`/api/creator/sessions/${sessionId}/paths`),
                fetch(`/api/creator/sessions/${sessionId}/assignments`),
                fetch(`/api/creator/examiners`),
            ]);

            if (!pathsRes.ok)       throw new Error(`Paths API error ${pathsRes.status}`);
            if (!assignmentsRes.ok) throw new Error(`Assignments API error ${assignmentsRes.status}`);
            if (!examinersRes.ok)   throw new Error(`Examiners API error ${examinersRes.status}`);

            const paths       = await pathsRes.json();
            const assignments = await assignmentsRes.json();
            const examiners   = await examinersRes.json();

            /* ── Lookup maps ─────────────────────────────────────────────── */
            const examinerById = {};
            examiners.forEach(e => { examinerById[e.id] = e; });

            const assignByStation = {};
            assignments.forEach(a => {
                assignByStation[a.station_id] = {
                    ...a,
                    examiner: examinerById[a.examiner_id] || null,
                };
            });

            const stationToPath = {};
            paths.forEach(path => {
                (path.stations || []).forEach(s => { stationToPath[s.id] = path.name; });
            });

            /* ── Stats ───────────────────────────────────────────────────── */
            const totalPaths    = paths.length;
            const totalStations = paths.reduce((n, p) => n + (p.stations || []).length, 0);
            const totalStudents = paths.reduce((n, p) => n + (p.students || []).length, 0);
            const assignedIds   = new Set(assignments.map(a => a.examiner_id).filter(Boolean));
            const totalExaminers = assignedIds.size;

            /* ── Report metadata ─────────────────────────────────────────── */
            const generatedAt = fmtNow();
            const reportId    = genReportId(sessionId);
            const dateTag     = new Date().toISOString().split('T')[0].replace(/-/g, '');
            const filename    = `Session_Report_${safeFilename(meta.sessionName)}_${dateTag}.pdf`;

            /* ── Init jsPDF ──────────────────────────────────────────────── */
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

            const arabicReady = await loadArabicFont(doc);

            const PAGE_W = doc.internal.pageSize.getWidth();
            const MARGIN = 12;
            const CONT_W = PAGE_W - MARGIN * 2;

            let y = 38;

            /* ════════════════════════════════════════════════════════════ */
            /*  SECTION 1 – SESSION OVERVIEW                               */
            /* ════════════════════════════════════════════════════════════ */
            y = drawSectionTitle(doc, y, 1, 'Session Overview');

            const statusColor = STATUS_COLOR[meta.sessionStatus] || C.dgray;
            const CARD_H  = 20;
            const CARD_GAP = 3;
            const CARD_W  = (CONT_W - CARD_GAP * 3) / 4;

            // Row 1: Exam Name | Session Name | Date | Status
            const row1Cards = [
                { label: 'Exam Name',    value: meta.examName                   },
                { label: 'Session Name', value: meta.sessionName                },
                { label: 'Session Date', value: fmtDate(meta.sessionDate)       },
                { label: 'Status',       value: capitalize(meta.sessionStatus), isStatus: true },
            ];

            row1Cards.forEach((card, i) => {
                const cx = MARGIN + i * (CARD_W + CARD_GAP);
                if (card.isStatus) {
                    doc.setFillColor(...statusColor);
                    doc.roundedRect(cx, y, CARD_W, CARD_H, 2, 2, 'F');
                    doc.setFontSize(6.5);
                    doc.setFont('helvetica', 'normal');
                    doc.setTextColor(...C.white);
                    doc.text('Status', cx + 3, y + 6);
                    doc.setFontSize(10);
                    doc.setFont('helvetica', 'bold');
                    doc.text(card.value, cx + 3, y + 14);
                } else {
                    drawInfoCard(doc, cx, y, CARD_W, CARD_H, card.label, card.value);
                }
            });
            y += CARD_H + 5;

            // Row 2: Course | Department | Report ID  (only if data present)
            if (meta.courseName || meta.department) {
                const R2W = (CONT_W - CARD_GAP * 2) / 3;
                const row2 = [
                    { label: 'Course',     value: meta.courseName || 'N/A' },
                    { label: 'Department', value: meta.department  || 'N/A' },
                    { label: 'Report ID',  value: reportId                  },
                ];
                row2.forEach((card, i) => {
                    drawInfoCard(doc, MARGIN + i * (R2W + CARD_GAP), y, R2W, CARD_H, card.label, card.value);
                });
                y += CARD_H + 5;
            }

            y += 5;

            /* ════════════════════════════════════════════════════════════ */
            /*  SECTION 2 – PARTICIPANTS SUMMARY                           */
            /* ════════════════════════════════════════════════════════════ */
            y = checkPageBreak(doc, y, 250);
            y = drawSectionTitle(doc, y, 2, 'Participants Summary');

            const statsCards = [
                { label: 'Total Students',   value: totalStudents  },
                { label: 'Examiners',        value: totalExaminers },
                { label: 'Total Stations',   value: totalStations  },
                { label: 'Paths / Circuits', value: totalPaths     },
            ];
            statsCards.forEach((card, i) => {
                drawInfoCard(doc, MARGIN + i * (CARD_W + CARD_GAP), y, CARD_W, CARD_H, card.label, card.value);
            });
            y += CARD_H + 10;

            /* ════════════════════════════════════════════════════════════ */
            /*  SECTION 3 – EXAMINER ASSIGNMENTS                           */
            /* ════════════════════════════════════════════════════════════ */
            y = checkPageBreak(doc, y, 200);
            y = drawSectionTitle(doc, y, 3, 'Examiner Assignments');

            if (assignments.length === 0) {
                doc.setFontSize(8.5);
                doc.setFont('helvetica', 'italic');
                doc.setTextColor(...C.dgray);
                doc.text('No examiner assignments have been recorded for this session.', MARGIN, y + 5);
                y += 12;
            } else {
                const sortedAssignments = [...assignments].sort((a, b) => {
                    const pa = stationToPath[a.station_id] || '';
                    const pb = stationToPath[b.station_id] || '';
                    if (pa !== pb) return pa.localeCompare(pb);
                    return (a.station_number || 0) - (b.station_number || 0);
                });

                const examinerRows = sortedAssignments.map(a => {
                    const ex = examinerById[a.examiner_id];
                    const rawName = ex ? ex.full_name : (a.examiner_name || '—');
                    return [
                        rawName,
                        stationToPath[a.station_id] ? `Path ${stationToPath[a.station_id]}` : '—',
                        a.station_name   || '—',
                        a.station_number != null ? String(a.station_number) : '—',
                    ];
                });

                doc.autoTable({
                    startY: y,
                    margin: { left: MARGIN, right: MARGIN },
                    head: [['Examiner Name', 'Path', 'Station Name', 'Stn #']],
                    body: examinerRows,
                    theme: 'grid',
                    styles:      { fontSize: 8, cellPadding: 2.8, textColor: [40, 40, 50], lineColor: C.mgray, lineWidth: 0.2 },
                    headStyles:  { fillColor: C.navy, textColor: C.white, fontSize: 8, fontStyle: 'bold' },
                    alternateRowStyles: { fillColor: C.lgray },
                    columnStyles: {
                        1: { cellWidth: 30, halign: 'center' },
                        3: { cellWidth: 16, halign: 'center' },
                    },
                    showHead: 'everyPage',
                    rowPageBreak: 'avoid',
                    didParseCell(data) {
                        if (data.section !== 'body' || data.column.index !== 0) return;
                        const raw = String(data.cell.raw || '');
                        if (!arabicReady || !hasArabic(raw)) return;
                        data.cell.text          = [processArabicText(raw)];
                        data.cell.styles.halign = 'right';
                        data.cell.styles.font   = 'Amiri';
                    },
                });

                y = doc.lastAutoTable.finalY + 8;
            }

            /* ════════════════════════════════════════════════════════════ */
            /*  SECTION 4 – PATHS & STATIONS BREAKDOWN                     */
            /* ════════════════════════════════════════════════════════════ */
            y = checkPageBreak(doc, y, 220);
            y = drawSectionTitle(doc, y, 4, 'Paths & Stations Breakdown');

            if (paths.length === 0) {
                doc.setFontSize(8.5);
                doc.setTextColor(...C.dgray);
                doc.setFont('helvetica', 'italic');
                doc.text('No paths defined for this session.', MARGIN, y + 5);
                y += 12;
            } else {
                paths.forEach((path) => {
                    const stations = path.stations || [];
                    y = checkPageBreak(doc, y, 210);

                    // Path sub-header
                    doc.setFillColor(...C.navy2);
                    doc.roundedRect(MARGIN, y, CONT_W, 7.5, 1.5, 1.5, 'F');
                    doc.setTextColor(...C.white);
                    doc.setFont('helvetica', 'bold');
                    doc.setFontSize(8.5);
                    const rotMin = path.rotation_minutes ? `${path.rotation_minutes} min/station` : '—';
                    doc.text(
                        `Path ${path.name}   ·   ${stations.length} station(s)   ·   ${path.student_count || 0} student(s)   ·   ${rotMin}`,
                        MARGIN + 4, y + 5
                    );
                    y += 9;

                    if (stations.length === 0) {
                        doc.setFontSize(7.5);
                        doc.setTextColor(...C.dgray);
                        doc.setFont('helvetica', 'italic');
                        doc.text('No stations configured for this path.', MARGIN + 4, y + 4);
                        y += 10;
                        return;
                    }

                    const stationRows = stations.map((s, idx) => {
                        const asgn = assignByStation[s.id];
                        const durMin = s.duration_minutes || path.rotation_minutes || null;
                        const examinerName = asgn
                            ? (asgn.examiner ? asgn.examiner.full_name : (asgn.examiner_name || '—'))
                            : 'Unassigned';
                        return [
                            `Path ${path.name}`,
                            String(s.station_number != null ? s.station_number : idx + 1),
                            s.name || '—',
                            durMin ? `${durMin} min` : '—',
                            examinerName,
                        ];
                    });

                    doc.autoTable({
                        startY: y,
                        margin: { left: MARGIN, right: MARGIN },
                        head: [['Path', 'Stn #', 'Station Name', 'Duration', 'Assigned Examiner']],
                        body: stationRows,
                        theme: 'grid',
                        styles:      { fontSize: 8, cellPadding: 2.8, textColor: [40, 40, 50], lineColor: C.mgray, lineWidth: 0.2 },
                        headStyles:  { fillColor: C.navy, textColor: C.white, fontSize: 8, fontStyle: 'bold', halign: 'center' },
                        alternateRowStyles: { fillColor: C.lgray },
                        columnStyles: {
                            0: { cellWidth: 22, halign: 'center' },
                            1: { cellWidth: 14, halign: 'center' },
                            3: { cellWidth: 24, halign: 'center' },
                            4: { cellWidth: 52 },
                        },
                        showHead: 'everyPage',
                        rowPageBreak: 'avoid',
                        didParseCell(data) {
                            if (data.section !== 'body' || data.column.index !== 4) return;
                            const raw = String(data.cell.raw || '');
                            if (!arabicReady || !hasArabic(raw)) return;
                            data.cell.text          = [processArabicText(raw)];
                            data.cell.styles.halign = 'right';
                            data.cell.styles.font   = 'Amiri';
                        },
                    });

                    y = doc.lastAutoTable.finalY + 6;
                });
            }

            /* ════════════════════════════════════════════════════════════ */
            /*  SECTION 5 – STUDENT LIST                                   */
            /* ════════════════════════════════════════════════════════════ */
            y = checkPageBreak(doc, y, 200);
            y = drawSectionTitle(doc, y, 5, 'Student List');

            const studentRows = [];
            paths.forEach(path => {
                const stations = (path.stations || []).slice().sort(
                    (a, b) => (a.station_number || 0) - (b.station_number || 0)
                );
                (path.students || []).forEach((stu, idx) => {
                    let startStation = '—';
                    if (stations.length > 0) {
                        const si = idx % stations.length;
                        const st = stations[si];
                        startStation = st ? `${st.station_number || si + 1}. ${st.name}` : '—';
                    }
                    studentRows.push([
                        stu.full_name      || '—',
                        stu.student_number || '—',
                        `Path ${path.name}`,
                        startStation,
                        capitalize(stu.status || 'registered'),
                    ]);
                });
            });

            studentRows.sort((a, b) => {
                const na = parseInt(a[1]) || 0;
                const nb = parseInt(b[1]) || 0;
                return na - nb;
            });

            if (studentRows.length === 0) {
                doc.setFontSize(8.5);
                doc.setFont('helvetica', 'italic');
                doc.setTextColor(...C.dgray);
                doc.text('No students enrolled in this session.', MARGIN, y + 5);
                y += 12;
            } else {
                doc.autoTable({
                    startY: y,
                    margin: { left: MARGIN, right: MARGIN },
                    head: [['Full Name', 'Student ID', 'Assigned Path', 'Starting Station', 'Status']],
                    body: studentRows,
                    theme: 'grid',
                    styles:      { fontSize: 8, cellPadding: 2.8, textColor: [40, 40, 50], lineColor: C.mgray, lineWidth: 0.2 },
                    headStyles:  { fillColor: C.navy, textColor: C.white, fontSize: 8, fontStyle: 'bold' },
                    alternateRowStyles: { fillColor: C.lgray },
                    columnStyles: {
                        1: { cellWidth: 32, halign: 'center' },
                        2: { cellWidth: 28, halign: 'center' },
                        4: { cellWidth: 24, halign: 'center' },
                    },
                    showHead: 'everyPage',
                    rowPageBreak: 'avoid',
                    didParseCell(data) {
                        if (data.section !== 'body' || data.column.index !== 0) return;
                        const raw = String(data.cell.raw || '');
                        if (!arabicReady || !hasArabic(raw)) return;
                        data.cell.text          = [processArabicText(raw)];
                        data.cell.styles.halign = 'right';
                        data.cell.styles.font   = 'Amiri';
                    },
                });

                y = doc.lastAutoTable.finalY + 5;
            }

            /* ════════════════════════════════════════════════════════════ */
            /*  POST-RENDER: paint header + footer on every page           */
            /* ════════════════════════════════════════════════════════════ */
            const totalPages = doc.internal.getNumberOfPages();
            for (let p = 1; p <= totalPages; p++) {
                doc.setPage(p);
                paintPageHeader(doc, meta, generatedAt, reportId, p, totalPages);
                paintPageFooter(doc, p, totalPages);
            }

            doc.save(filename);

        } catch (err) {
            console.error('[session-report-pdf] Error:', err);
            alert('Failed to generate session report:\n' + err.message);
        } finally {
            if (btn) {
                btn.disabled  = false;
                btn.innerHTML = originalLabel;
            }
        }
    }

    global.generateSessionReport = generateSessionReport;

})(window);