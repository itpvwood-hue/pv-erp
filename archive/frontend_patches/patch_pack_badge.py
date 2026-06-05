html = open('index.html', encoding='utf-8').read()
old = "      <td>${lineBadge(l.production_line)}</td>\n      <td>${fmt(l.quantity)}</td>\n      <td>${fmt(l.unit_price)}</td>"
badge = '<span class=\\"badge bg-success-subtle text-success border border-success\\" style=\\"font-size:.7rem\\"><i class=\\"bi bi-box me-1\\"></i>${l.packing_sku_code}</span>'
new = "      <td>${lineBadge(l.production_line)}${l.packing_sku_code?' " + badge + "':''}</td>\n      <td>${fmt(l.quantity)}</td>\n      <td>${fmt(l.unit_price)}</td>"
if old in html:
    html = html.replace(old, new, 1)
    open('index.html', 'w', encoding='utf-8').write(html)
    print('packing badge added')
else:
    print('pattern not found')
