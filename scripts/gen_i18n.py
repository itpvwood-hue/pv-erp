"""Regenerate the I18N dict in frontend/js/i18n.js from a translations xlsx.

Usage: python scripts/gen_i18n.py "<path-to-xlsx>"
The xlsx must have columns: ID, Status, Used in, English, Thai, Chinese (notes).
Replaces only the `const I18N = { ... };` literal; header comments + all helper
code below it are preserved untouched.
"""
import sys, io, json, re
import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

XLSX = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\PV_Natthapat\Downloads\ERP translations(1).xlsx"
JS = r"frontend\js\i18n.js"

wb = openpyxl.load_workbook(XLSX, read_only=True)
rows = list(wb['Translations'].iter_rows(values_only=True))
data = {}
for r in rows[1:]:
    en = r[3]
    if en is None or not str(en).strip():
        continue
    en = str(en)
    th = '' if r[4] is None else str(r[4])
    zh = '' if r[5] is None else str(r[5])
    data[en] = {'th': th, 'zh': zh}

# Compare against existing dict keys so we never silently drop one.
txt = open(JS, encoding='utf-8').read()
m = re.search(r"const I18N = \{", txt)
start = m.start()
end = txt.index("\n};", start) + len("\n};")
block = txt[start:end]
key_pat = re.compile(r"^\s*'((?:[^'" + "\\\\" + r"]|" + "\\\\" + r".)*)'\s*:", re.M)
existing = set(key_pat.findall(block))
missing = sorted(k for k in existing if k not in data)
print("existing dict keys:", len(existing))
print("spreadsheet keys  :", len(data))
print("existing keys NOT in spreadsheet (will be ADDED back):", len(missing))
for k in missing:
    print("   +", json.dumps(k, ensure_ascii=False))

# Add any hand-written keys the spreadsheet lacks, preserving their values.
val_pat = re.compile(
    r"'((?:[^'" + "\\\\" + r"]|" + "\\\\" + r".)*)'\s*:\s*\{[^}]*?th:\s*'((?:[^'" + "\\\\" + r"]|" + "\\\\" + r".)*)'[^}]*?zh:\s*'((?:[^'" + "\\\\" + r"]|" + "\\\\" + r".)*)'",
    re.S)
old_vals = {k: {'th': th, 'zh': zh} for k, th, zh in val_pat.findall(block)}
for k in missing:
    if k in old_vals:
        data[k] = old_vals[k]

# Emit a fresh, JSON-safe object literal (sorted for stable diffs).
lines = ["const I18N = {"]
for k in sorted(data, key=lambda s: s.lower()):
    kk = json.dumps(k, ensure_ascii=False)
    th = json.dumps(data[k]['th'], ensure_ascii=False)
    zh = json.dumps(data[k]['zh'], ensure_ascii=False)
    lines.append(f"  {kk}: {{th: {th}, zh: {zh}}},")
lines.append("}")
new_block = "\n".join(lines) + ";"
# old block ends with "\n};" -> our index(end) included the ';'? It included "\n};" only.
# Re-slice precisely: replace from 'const I18N = {' through the closing '};'.
end2 = txt.index("\n};", start) + len("\n};")
new_txt = txt[:start] + new_block + txt[end2:]
open(JS, 'w', encoding='utf-8', newline='\n').write(new_txt)
print("WROTE", JS, "->", len(data), "entries")
