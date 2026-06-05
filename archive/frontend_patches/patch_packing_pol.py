"""Decouple packing from BOM — move packing selection to PO line modal."""
import re

html = open('index.html', encoding='utf-8').read()

# ── 1. Load packing specs in openPoLineModal ──────────────────────────────────
OLD_OPEN = "  // Load FG list from /api/fg\n  const fgs = await api('/api/fg');\n  _polFgAll = fgs;"
NEW_OPEN = """  // Load FG list and packing specs in parallel
  const [fgs, packSpecs] = await Promise.all([
    api('/api/fg'),
    api('/api/packing-skus').catch(()=>[]),
  ]);
  _polFgAll = fgs;
  // Populate packing dropdown
  const packSel = document.getElementById('pol-packing-id');
  packSel.innerHTML = '<option value="">\\u2014 No packing selected \\u2014</option>' +
    packSpecs.map(p=>`<option value="${p.id}">${p.code}${p.customer?' ('+p.customer+')':''}</option>`).join('');"""

assert OLD_OPEN in html, "openPoLineModal load block not found"
html = html.replace(OLD_OPEN, NEW_OPEN, 1)
print("openPoLineModal: packing load added")

# ── 2. Remove packing_sku_code from FG info strip ────────────────────────────
OLD_FG_INFO = "    &nbsp;|&nbsp; <span class=\"text-muted\">${fg.packing_sku_code||'\\u2014'}</span>`;"
if OLD_FG_INFO in html:
    html = html.replace(OLD_FG_INFO, '`;', 1)
    print("onPolFgSelect: packing_sku_code removed from FG info")
else:
    # Try without unicode escape
    for variant in ["&nbsp;|&nbsp; <span class=\"text-muted\">${fg.packing_sku_code||'—'}</span>`;"]:
        if variant in html:
            html = html.replace(variant, '`;', 1)
            print("onPolFgSelect: packing_sku_code removed (variant)")
            break
    else:
        print("WARN: packing_sku_code in fg info not found")

# ── 3. Add packing_sku_id to savePoLine body ─────────────────────────────────
OLD_BODY = "  const body={\n    production_line:document.getElementById('pol-line').value,\n    quantity:qty,\n    unit_price:parseFloat(document.getElementById('pol-price').value)||0,\n    notes:document.getElementById('pol-notes').value\n  };"
NEW_BODY = "  const polPackId = document.getElementById('pol-packing-id').value ? parseInt(document.getElementById('pol-packing-id').value) : null;\n  const body={\n    production_line:document.getElementById('pol-line').value,\n    quantity:qty,\n    unit_price:parseFloat(document.getElementById('pol-price').value)||0,\n    notes:document.getElementById('pol-notes').value,\n    packing_sku_id: polPackId,\n  };"
assert OLD_BODY in html, "savePoLine body not found"
html = html.replace(OLD_BODY, NEW_BODY, 1)
print("savePoLine: packing_sku_id added to body")

# ── 4. Reset packing dropdown when opening modal ──────────────────────────────
OLD_OPEN_RESET = "  document.getElementById('pol-fg-info').classList.add('d-none');"
NEW_OPEN_RESET = "  document.getElementById('pol-fg-info').classList.add('d-none');\n  document.getElementById('pol-packing-id').value='';"
# Only replace first occurrence (in openPoLineModal)
html = html.replace(OLD_OPEN_RESET, NEW_OPEN_RESET, 1)
print("openPoLineModal: packing reset added")

# ── 5. Update editPoLine signature and add packing set before modal show ──────
OLD_EDIT_SIG = "async function editPoLine(id, productId, sku, name, line, qty, price, notes){"
NEW_EDIT_SIG = "async function editPoLine(id, productId, sku, name, line, qty, price, notes, packingSkuId){"
assert OLD_EDIT_SIG in html, "editPoLine signature not found"
html = html.replace(OLD_EDIT_SIG, NEW_EDIT_SIG, 1)

# Add packing set before modal show
OLD_MODAL_SHOW = "  bootstrap.Modal.getOrCreateInstance(document.getElementById('poLineModal')).show();\n}"
NEW_MODAL_SHOW = (
    "  // Set packing dropdown\n"
    "  if(document.getElementById('pol-packing-id').options.length <= 1){\n"
    "    const pks = await api('/api/packing-skus').catch(()=>[]);\n"
    "    document.getElementById('pol-packing-id').innerHTML = '<option value=\"\">— No packing selected —</option>' +\n"
    "      pks.map(p=>`<option value=\"${p.id}\">${p.code}${p.customer?' ('+p.customer+')':''}</option>`).join('');\n"
    "  }\n"
    "  document.getElementById('pol-packing-id').value = packingSkuId || '';\n"
    "  bootstrap.Modal.getOrCreateInstance(document.getElementById('poLineModal')).show();\n"
    "}"
)
assert OLD_MODAL_SHOW in html, "editPoLine modal show not found"
html = html.replace(OLD_MODAL_SHOW, NEW_MODAL_SHOW, 1)
print("editPoLine: packing_sku_id param + dropdown set added")

# ── 6. Find and update editPoLine call in PO card render ─────────────────────
# Find the onclick call pattern
old_call_pat = re.compile(
    r"onclick=\"editPoLine\(\$\{l\.id\},\$\{l\.product_id\},'(\$\{l\.sku\})','(\$\{l\.product_name\})','(\$\{l\.production_line\})',\$\{l\.quantity\},\$\{l\.unit_price\},'(\$\{[^}]+\})'\)\""
)
match = old_call_pat.search(html)
if match:
    old = match.group(0)
    # Add packing_sku_id arg at end before closing paren
    new = old[:-1] + ",${l.packing_sku_id||''})\""
    html = html.replace(old, new, 1)
    print("editPoLine call: packing_sku_id arg added")
else:
    # Try simpler pattern
    idx = html.find("onclick=\"editPoLine(${l.id},${l.product_id},")
    if idx >= 0:
        end = html.index(')"', idx) + 2
        snippet = html[idx:end]
        print("Found call (manual):", repr(snippet[:150]))
        new_snippet = snippet[:-2] + ",${l.packing_sku_id||''})\""
        html = html.replace(snippet, new_snippet, 1)
        print("editPoLine call: packing_sku_id arg added (manual)")
    else:
        print("WARN: editPoLine call not found")

# ── 7. Remove packPill from renderBom card ────────────────────────────────────
PACK_PILL_PAT = r'\n\s*<div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">PACKING</small>\$\{packPill\(r\.packing\)\}</div>'
html, n = re.subn(PACK_PILL_PAT, '', html)
print("renderBom packPill removed:", n, "occurrence(s)")

# ── 8. Remove packing_sku_code from saveBomBuilder body ──────────────────────
html = re.sub(r"\n\s*packing_sku_code:\s*_bbPicked\.pack\s*\?[^,]+,\n?", '\n', html)
print("saveBomBuilder: packing_sku_code removed")

# ── 9. Remove pack from comp arrays ──────────────────────────────────────────
html = html.replace("['base','faceV','backV','faceG','backG','pack']",
                    "['base','faceV','backV','faceG','backG']")
print("comp arrays: pack removed")

# ── 10. Remove pack from _bbMats and bbLoadFg packing block ──────────────────
# In loadBomBuilder, remove pack from _bbMats
OLD_BB_MATS = "  _bbMats = {\n    base:  mats.filter(m=>m.type==='core_board'),\n    faceV: mats.filter(m=>m.type==='veneer_sheet'),\n    backV: mats.filter(m=>m.type==='veneer_sheet'),\n    faceG: glues.filter(m=>m.type==='glue_formula'),\n    backG: glues.filter(m=>m.type==='glue_formula'),\n    pack:  packing,\n  };"
NEW_BB_MATS = "  _bbMats = {\n    base:  mats.filter(m=>m.type==='core_board'),\n    faceV: mats.filter(m=>m.type==='veneer_sheet'),\n    backV: mats.filter(m=>m.type==='veneer_sheet'),\n    faceG: glues.filter(m=>m.type==='glue_formula'),\n    backG: glues.filter(m=>m.type==='glue_formula'),\n  };"
if OLD_BB_MATS in html:
    html = html.replace(OLD_BB_MATS, NEW_BB_MATS, 1)
    print("loadBomBuilder: pack removed from _bbMats")

# Remove the packing API call from loadBomBuilder (no longer needed)
OLD_PACK_API = "    api('/api/packing-skus').catch(()=>[]),\n  ]);\n  _bbMats = {"
NEW_PACK_API = "  ]);\n  _bbMats = {"
if OLD_PACK_API in html:
    # Also remove packing from the destructure
    html = html.replace(
        "  const [mats, glues, packing] = await Promise.all([\n    api('/api/materials').catch(()=>[]),\n    api('/api/materials?include_formulas=true').catch(()=>[]),\n    api('/api/packing-skus').catch(()=>[]),\n  ]);",
        "  const [mats, glues] = await Promise.all([\n    api('/api/materials').catch(()=>[]),\n    api('/api/materials?include_formulas=true').catch(()=>[]),\n  ]);",
        1
    )
    print("loadBomBuilder: packing-skus API call removed")

# Remove bbLoadFg packing block
OLD_PACK_BOM_LOAD = (
    "    if(bom.packing){\n"
    "      if(!_bbMats['pack'].find(m=>m.code===bom.packing.code))\n"
    "        _bbMats['pack'].unshift({code:bom.packing.code, name:bom.packing.name, customer:bom.packing.customer});\n"
    "      bbRenderOptions('pack', _bbMats['pack']);\n"
    "      const sel = document.getElementById('bb-select-pack');\n"
    "      if(sel) sel.value = bom.packing.code;\n"
    "      bbPick('pack', bom.packing.code);\n"
    "    }\n"
)
if OLD_PACK_BOM_LOAD in html:
    html = html.replace(OLD_PACK_BOM_LOAD, '', 1)
    print("bbLoadFg: packing block removed")

# ── 11. Show packing on PO line cards ────────────────────────────────────────
# Find where PO lines are rendered and add packing badge
# The PO line cards are rendered in selectPo function
PACK_BADGE_OLD = "deletePoLine(${l.id})"
# Just after the PO line card content, add packing badge
# Find the right spot — after the unit_price badge
OLD_LINE_CARD = r"<span class=\"badge bg-secondary\">\$\{l\.production_line\}</span>"
match2 = re.search(OLD_LINE_CARD, html)
if match2:
    old_span = match2.group(0)
    new_span = old_span + "${l.packing_sku_code ? `<span class=\"badge bg-success-subtle text-success border border-success ms-1\"><i class=\"bi bi-box me-1\"></i>${l.packing_sku_code}</span>` : ''}"
    html = html.replace(old_span, new_span, 1)
    print("PO line card: packing badge added")
else:
    print("WARN: PO line card production_line badge not found")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print()
print("Final checks:")
print("  packing_sku_id in savePoLine:", 'packing_sku_id' in html)
print("  pol-packing-id select:", 'pol-packing-id' in html)
print("  packPill in BOM card:", 'packPill(r.packing)' in html)
print("  packing_sku_code in saveBomBuilder body:", "'packing_sku_code'" in html)
print("  editPoLine packing param:", 'packingSkuId' in html)
print("  packing badge on PO line:", 'packing_sku_code' in html and 'bi-box' in html)
