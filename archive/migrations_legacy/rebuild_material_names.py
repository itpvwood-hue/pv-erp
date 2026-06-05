"""
rebuild_material_names.py
--------------------------
Regenerates the `name` field for all materials that have structured
spec columns, using a consistent concatenated format.

Board  format : {board_type} {glue_type} {thick}mm x {width}x{length}mm
Veneer format : {species} {cut} {thick}mm x {width}x{length}mm {grade} {matching}

Only updates rows that actually have specs filled in; legacy rows
without specs are left untouched.
"""
import sys, sqlite3
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

DB = Path(__file__).parent.parent / 'erp.db'

def fmt_num(v):
    """Format float: show as int when whole number (12.0 -> '12'), else as-is."""
    if v is None: return None
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)

def board_name(r):
    """Build canonical board description from structured fields."""
    parts = []
    bt = (r['board_type'] or '').strip()
    gt = (r['glue_type']  or '').strip()
    if bt: parts.append(bt)
    # Only add glue if not already included in board_type
    if gt and gt.upper() not in bt.upper():
        parts.append(gt)
    t = fmt_num(r['thickness_mm'])
    w = fmt_num(r['width_mm'])
    l = fmt_num(r['length_mm'])
    if t:       parts.append(t + 'mm')
    if w and l: parts.append(w + 'x' + l + 'mm')
    return ' '.join(parts)

def veneer_name(r):
    """Build canonical veneer description from structured fields."""
    parts = []
    sp  = (r['species']  or '').strip()
    cut = (r['cut_type'] or '').strip()
    gr  = (r['grade']    or '').strip()
    mt  = (r['matching'] or '').strip()
    t   = fmt_num(r['thickness_mm'])
    w   = fmt_num(r['width_mm'])
    l   = fmt_num(r['length_mm'])
    if sp:      parts.append(sp)
    if cut:     parts.append(cut)
    if t:       parts.append(t + 'mm')
    if w and l: parts.append(w + 'x' + l + 'mm')
    if gr:      parts.append(gr)
    if mt:      parts.append(mt)
    return ' '.join(parts)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA journal_mode=WAL')

# ── Boards: only update rows with board_type filled ───────────────────────────
boards = conn.execute("""
    SELECT id, code, board_type, glue_type, thickness_mm, width_mm, length_mm
    FROM materials
    WHERE type='core_board' AND board_type IS NOT NULL AND board_type != ''
""").fetchall()

upd_b = 0
for r in boards:
    name = board_name(r)
    if name:
        conn.execute("UPDATE materials SET name=? WHERE id=?", (name, r['id']))
        upd_b += 1

# ── Veneers: only update rows with species filled ─────────────────────────────
veneers = conn.execute("""
    SELECT id, code, species, cut_type, thickness_mm, width_mm, length_mm, grade, matching
    FROM materials
    WHERE type='veneer_sheet' AND species IS NOT NULL AND species != ''
""").fetchall()

upd_v = 0
for r in veneers:
    name = veneer_name(r)
    if name:
        conn.execute("UPDATE materials SET name=? WHERE id=?", (name, r['id']))
        upd_v += 1

conn.commit()
conn.close()

print(f'Updated {upd_b} board names, {upd_v} veneer names.')
print()
print('Board format  : {board_type} {glue_type} {thick}mm x {width}x{length}mm')
print('Veneer format : {species} {cut} {thick}mm x {width}x{length}mm {grade} {matching}')
