path = r"d:\Fawzi Osce app\OSCE_PROJECT\templates\creator\sessions\detail.html"
with open(path, encoding="utf-8") as f:
    c = f.read()

# Fix: remove the bad STUDENTS_SLOT line injected by previous powershell attempt
import re
c = re.sub(
    r'    </div>`n`n    <!-- STUDENTS_SLOT`n`n    <!-- ',
    '    <!-- ',
    c
)

print("STUDENTS_SLOT still present:", "STUDENTS_SLOT" in c)
print("col-lg-9 close present:", '    </div>\n\n    <!-- \u2550\u2550\u2550 Column:' in c)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)
print("Saved.")
