"""
fix_mat_names.py
1. Update material names to proper English descriptions
2. Retype packaging -> consumable
"""
import sqlite3, csv, re
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "erp.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")

# ── Load scraped descriptions ──────────────────────────────────
desc_map = {}
with open("C:/Users/PV_Natthapat/Downloads/files_extracted/bom_migration/pv_erp_migration/data/scraped_materials.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        desc_map[r["code"]] = {"desc": r.get("description",""), "name_th": r.get("name_th","")}

# ── Helpers ────────────────────────────────────────────────────
def extract_english(text):
    """Pull the English spec out of a mixed Thai/English/Chinese description."""
    if not text: return ""
    text = text.strip().replace("\n"," ")
    if text and text[0].isascii() and text[0].isalpha():
        return text  # already English
    # Find first stretch of ASCII letters/digits/symbols that looks meaningful
    m = re.search(r'[A-Za-z0-9][A-Za-z0-9 \.\-\/\#\*\(\)mm]+', text)
    return m.group(0).strip() if m else ""

BOARD_PREFIX = {
    "BMC": "MDF",
    "BPC": "PB",        # Particle Board
    "BSC": "MDF",
    "BXC": "VCMX",      # Cross-core
    "BVC": "Platform",
    "BFC": "Platform",
    "BF1": "Platform",
}

def board_type(code):
    for pfx, label in BOARD_PREFIX.items():
        if code.upper().startswith(pfx):
            return label
    return "Board"

def board_dims(code):
    """Try to extract thickness from code (e.g. BMCN2511 -> 2.5mm)."""
    m = re.search(r'(?:BMC|BPC|BSC|BXC|BVC|BFC|BF1)[A-Z](\d{2,3})', code.upper())
    if m:
        digits = m.group(1)
        if len(digits) == 2:
            return f"{int(digits[0])}.{digits[1]}mm"
        elif digits.startswith("X") or len(digits) == 3:
            return f"{int(digits[:2])}.{digits[2]}mm"
    return ""

SPECIES_MAP = {
    "WBR": "W.Birch", "NBR": "N.Birch", "OAK": "Oak", "ROP": "R.Oak",
    "WOK": "W.Oak",  "WAL": "Walnut",  "WAP": "Walnut PC",
    "MAP": "Maple",  "WMA": "W.Maple", "NMA": "N.Maple",
    "CHP": "Cherry", "TEA": "Teak",    "BEE": "Beech",
    "ALP": "Alder",  "HIP": "Hickory", "ASH": "Ash",
    "BIR": "Birch",  "POP": "Poplar",  "ELM": "Elm",
    "KNP": "Knotty Pine", "CEP": "Cedar", "EUC": "Eucalyptus",
    "MOZ": "MOB",    "SAN": "Santos",  "ROB": "R.Oak B",
    "ROC": "R.Oak C","ROS": "R.Oak SM","WMP": "W.Maple",
}
CUT_MAP = {"W":"WPF","M":"MPF","B":"BM","P":"PM","S":"SM","Z":"Z-splice","R":"RC","D":"D+"}
GRADE_MAP = {"A":"A","B":"B","C":"C","F":"F","1":"#1","2":"#2","3":"#3","4":"#4","U":"UV"}

def parse_veneer_code(code):
    """XWBRWB01 -> W.Birch WPF Grade B"""
    if not code.startswith("X") or len(code) < 7:
        return ""
    species_raw = code[1:4].upper()
    cut_raw     = code[4].upper() if len(code) > 4 else ""
    grade_raw   = code[5].upper() if len(code) > 5 else ""
    species = SPECIES_MAP.get(species_raw, species_raw)
    cut     = CUT_MAP.get(cut_raw, cut_raw)
    grade   = GRADE_MAP.get(grade_raw, grade_raw)
    return f"{species} {cut} Gr.{grade}" if cut else f"{species} Gr.{grade}"

# ── Step 1: Update core board names ────────────────────────────
print("Step 1: Core board names ...")
updated = 0
for r in conn.execute("SELECT id, code, name, name_th FROM materials WHERE type='core_board' AND code!=''").fetchall():
    d = desc_map.get(r["code"], {})
    desc_en = extract_english(d.get("desc",""))
    btype   = board_type(r["code"])
    dims    = board_dims(r["code"])
    # Build name: e.g. "MDF CARB P2  ·  2.5mm"  or "PlatformAX CARB P2"
    if desc_en and desc_en not in ("MDF CARB P2","PB CARB P2"):
        new_name = desc_en  # specific like "PlatformAX CARB P2"
    else:
        new_name = f"{btype} CARB P2"
    if dims:
        new_name = f"{new_name}  {dims}"
    conn.execute("UPDATE materials SET name=? WHERE id=?", (new_name, r["id"]))
    updated += 1
conn.commit()
print(f"  Updated {updated} core board names")

# ── Step 2: Update veneer names ────────────────────────────────
print("Step 2: Veneer names ...")
updated = 0
for r in conn.execute("SELECT id, code, name, name_th FROM materials WHERE type='veneer_sheet' AND code!='' AND code LIKE 'X%'").fetchall():
    d = desc_map.get(r["code"], {})
    # Try CSV description first (strip Thai prefix)
    desc_en = extract_english(d.get("desc",""))
    # Parse code as fallback
    code_name = parse_veneer_code(r["code"])
    # Prefer desc if it has meaningful English, else use code parse
    if desc_en and len(desc_en) > 3 and any(c.isalpha() for c in desc_en):
        new_name = desc_en
    elif code_name:
        new_name = code_name
    else:
        new_name = r["name"] or r["code"]
    conn.execute("UPDATE materials SET name=? WHERE id=?", (new_name, r["id"]))
    updated += 1
conn.commit()
print(f"  Updated {updated} veneer names")

# ── Step 3: Retype packaging -> consumable ─────────────────────
print("Step 3: Retyping packaging -> consumable ...")
cur = conn.execute("UPDATE materials SET type='consumable' WHERE type='packaging'")
conn.commit()
print(f"  Retyped {cur.rowcount} records")

# Also retype edge_banding -> consumable (it's a packing consumable too)
# Actually keep edge_banding separate as it's a production consumable not packing

# ── Step 4: Verify ─────────────────────────────────────────────
print("\nVerification:")
for t in conn.execute("SELECT type, COUNT(*) n FROM materials GROUP BY type ORDER BY n DESC").fetchall():
    print(f"  {t['type']:<20} {t['n']}")

print("\nSample core boards:")
for r in conn.execute("SELECT code, name FROM materials WHERE type='core_board' AND code!='' LIMIT 6").fetchall():
    print(f"  {r['code']:<14} {r['name']}")

print("\nSample veneers:")
for r in conn.execute("SELECT code, name FROM materials WHERE type='veneer_sheet' AND code LIKE 'X%' ORDER BY code LIMIT 8").fetchall():
    print(f"  {r['code']:<14} {r['name']}")

print("\nSample consumables:")
for r in conn.execute("SELECT code, name FROM materials WHERE type='consumable' LIMIT 6").fetchall():
    print(f"  {r['code']:<14} {r['name'][:50] if r['name'] else ''}")

conn.close()
print("\nDone.")
