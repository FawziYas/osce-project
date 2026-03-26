"""
Restructure session detail layout:
  BEFORE:
    row
      col-lg-9 (paths)  [UNCLOSED - contains col-lg-3 and students as children]
        col-lg-3 (session info)
        col-12 > col-md-8 > students card
      /div (#row g-4 closes col-lg-9)
      [ROW IS UNCLOSED]

  AFTER:
    row
      col-lg-9 (paths + students stacked)
      col-lg-3 (session info)
    /row
"""

path = r"d:\Fawzi Osce app\OSCE_PROJECT\templates\creator\sessions\detail.html"
with open(path, encoding="utf-8") as f:
    content = f.read()

# ─── Locate anchors ───────────────────────────────────────────────────────────
ROW_OPEN   = '<div class="row gy-2 gx-4">'
# Paths card closes, then the col-lg-3 comment starts
PATHS_END  = '        </div>\n    <!-- \u2550\u2550\u2550 Column: Session Info + Examiners + Scores \u2550\u2550\u2550 -->'
COL3_OPEN  = '<div class="col-lg-3">'
COL3_CLOSE = '</div><!-- /col-lg-3 -->'
STU_FENCE_START = '\n    <!-- \u2550\u2550\u2550 Bottom row: Students full width \u2550\u2550\u2550 -->\n    <div class="col-12">\n    <!-- Students Panel -->\n    <div class="col-md-8" style="max-width:100%;flex:0 0 100%;">\n        <div class="card shadow-sm border-0 mb-4"'
STU_CARD_OPEN   = '        <div class="card shadow-sm border-0 mb-4"'
STU_COL12_CLOSE = '    </div>{# /col-12 students bottom row #}'
ROW_CLOSE  = '</div>{# /row g-4 #}'

# ─── Verify all anchors exist ─────────────────────────────────────────────────
for name, anchor in [("ROW_OPEN", ROW_OPEN), ("PATHS_END", PATHS_END),
                     ("COL3_OPEN", COL3_OPEN), ("COL3_CLOSE", COL3_CLOSE),
                     ("STU_FENCE_START", STU_FENCE_START),
                     ("STU_COL12_CLOSE", STU_COL12_CLOSE), ("ROW_CLOSE", ROW_CLOSE)]:
    idx = content.find(anchor)
    print(f"  {name}: {'FOUND at '+str(idx) if idx != -1 else '*** NOT FOUND ***'}")

print()

# ─── Extract the three parts ──────────────────────────────────────────────────
# 1. Everything before the row block (keep as-is)
row_start = content.find(ROW_OPEN)

# 2. Paths card HTML (content INSIDE col-lg-9, not including its opening tag)
col9_opening = '    <div class="col-lg-9">'
col9_open_end = content.find(col9_opening, row_start) + len(col9_opening)
paths_end_idx = content.find(PATHS_END)
paths_html = content[col9_open_end : paths_end_idx + len('        </div>')]
print(f"paths_html starts: {repr(paths_html[:60])}")
print(f"paths_html ends:   {repr(paths_html[-60:])}")

# 3. Session info col-lg-3 HTML (just the inner content between opening/closing tags)
col3_start = content.find(COL3_OPEN)
col3_end   = content.find(COL3_CLOSE) + len(COL3_CLOSE)
col3_full_html = content[col3_start : col3_end]
print(f"col3_full starts: {repr(col3_full_html[:60])}")
print(f"col3_full ends:   {repr(col3_full_html[-40:])}")

# 4. Students card — find the card open AFTER the STU_FENCE_START marker
stu_fence_idx = content.find(STU_FENCE_START)
stu_card_start = content.find(STU_CARD_OPEN, stu_fence_idx)
stu_col12_close_idx = content.find(STU_COL12_CLOSE)
# Students card HTML: from the card open to just before the col-12 closers
# The structure is:   students card </div>  </div>  </div>{# /col-12 #}
# We want just:       students card </div>
# The 2 extra </div>s are for col-md-8 and col-12
stu_html_with_wrappers = content[stu_card_start : stu_col12_close_idx + len(STU_COL12_CLOSE)]
# Remove trailing </div>\n    </div> (col-md-8 and col-12 wrappers at the end)
# The end of the actual students card is "        </div>" followed by "\n    </div>\n    </div>{# /col-12"
stu_card_end_marker = '        </div>\n    </div>\n    </div>{# /col-12 students bottom row #}'
idx_in_stu = stu_html_with_wrappers.find(stu_card_end_marker)
if idx_in_stu == -1:
    print("WARNING: could not find stu_card_end_marker, trying alternative")
    stu_card_end_marker = '        </div>\n    </div>\n    </div>{# /col-12'
    idx_in_stu = stu_html_with_wrappers.find(stu_card_end_marker)

stu_card_html = stu_html_with_wrappers[:idx_in_stu + len('        </div>')]
print(f"stu_card starts: {repr(stu_card_html[:80])}")
print(f"stu_card ends:   {repr(stu_card_html[-60:])}")

# ─── Build the new row block ──────────────────────────────────────────────────
row_close_end = content.find(ROW_CLOSE) + len(ROW_CLOSE)
before_row = content[:row_start]
after_row  = content[row_close_end:]

new_row = (
    '<div class="row gy-2 gx-4">\n'
    '    <!-- \u2550\u2550\u2550 Left: Rotation Paths + Students \u2550\u2550\u2550 -->\n'
    '    <div class="col-lg-9">\n'
    + paths_html + '\n'
    + '    <!-- Students Panel -->\n'
    + stu_card_html.replace(
        # Change mb-4 to mt-2 on the students card to remove gap
        'class="card shadow-sm border-0 mb-4"',
        'class="card shadow-sm border-0 mt-2"'
    ) + '\n'
    '    </div><!-- /col-lg-9 -->\n\n'
    '    <!-- \u2550\u2550\u2550 Right: Session Info + Examiners + Scores \u2550\u2550\u2550 -->\n'
    '    ' + col3_full_html + '\n\n'
    '</div>{# /row g-4 #}'
)

new_content = before_row + new_row + after_row

# ─── Verify result ────────────────────────────────────────────────────────────
row_count = new_content.count('<div class="row gy-2 gx-4">')
col9_count = new_content.count('<div class="col-lg-9">')
col3_count_open  = new_content.count('<div class="col-lg-3">')
row_close_count  = new_content.count('</div>{# /row g-4 #}')
print(f"\nVerification:")
print(f"  row opens:  {row_count}")
print(f"  col-lg-9:   {col9_count}")
print(f"  col-lg-3:   {col3_count_open}")
print(f"  row closes: {row_close_count}")
print(f"  col-12 students: {new_content.count('col-12 students')}")

if row_count == 1 and col9_count == 1 and col3_count_open >= 1 and row_close_count == 1:
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("\n✓ File saved successfully.")
else:
    print("\n✗ Verification failed — file NOT saved.")
