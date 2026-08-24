import json, os, re, sys
import pymupdf

SP = os.environ['SP']
SRC = sys.argv[1]
DST = sys.argv[2]

cells = json.load(open(os.path.join(SP, 'cells.json'), encoding='utf-8'))
tmap  = json.load(open(os.path.join(SP, 'map.json'), encoding='utf-8'))

# Helvetica is WinAnsi-encoded; map the few glyphs outside it.
SUBS = {'π': 'pi', '×': 'x', '℃': '°C', 'Ω': 'ohm',
        '→': '->', '≤': '<=', '≥': '>=', '‘': "'", '’': "'",
        '“': '"', '”': '"', '≥': '>='}
def latin(s):
    for k, v in SUBS.items():
        s = s.replace(k, v)
    return ''.join(ch if ord(ch) < 0x180 or ch in '–—' else '?' for ch in s)

doc = pymupdf.open(SRC)
PW = doc[0].rect.width

def vlines(page):
    """x positions of vertical rules on the page - the table column borders."""
    xs = []
    for d in page.get_drawings():
        for item in d['items']:
            if item[0] == 'l':
                a, b = item[1], item[2]
                if abs(a.x - b.x) < 0.6 and abs(a.y - b.y) > 3:
                    xs.append((a.x, min(a.y, b.y), max(a.y, b.y)))
            elif item[0] == 're':
                r = item[1]
                if r.height > 3:
                    xs.append((r.x0, r.y0, r.y1))
                    xs.append((r.x1, r.y0, r.y1))
    return xs
per_page = {}
for c in cells:
    if c['text'] in tmap:
        per_page.setdefault(c['page'], []).append(c)

stats = {'placed': 0, 'shrunk': 0, 'failed': 0}
for pno in sorted(per_page):
    page = doc[pno - 1]
    items = per_page[pno]
    rules = vlines(page)
    # right-hand limit: next cell on the same line, or the table border, whichever is nearer
    items.sort(key=lambda c: (round(c['bbox'][1], 0), c['bbox'][0]))
    for i, c in enumerate(items):
        x0, y0, x1, y1 = c['bbox']
        limit = PW - 28
        for other in items:
            ox0, oy0, ox1, oy1 = other['bbox']
            if other is c:
                continue
            # same line and to the right
            if abs(oy0 - y0) < max(3.0, (y1 - y0) * 0.6) and ox0 >= x1 - 0.5:
                limit = min(limit, ox0 - 1.5)
        ymid = (y0 + y1) / 2.0
        for rx, ry0, ry1 in rules:
            if rx >= x1 - 0.5 and ry0 - 1 <= ymid <= ry1 + 1:
                limit = min(limit, rx - 2.0)
        c['limit'] = max(x1, min(limit, PW - 8))

    # 1) strip original text without painting over gridlines or figures
    for c in items:
        page.add_redact_annot(pymupdf.Rect(*c['bbox']), fill=None)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    # 2) lay the English back into the same boxes
    for c in items:
        x0, y0, x1, y1 = c['bbox']
        en = latin(tmap[c['text']])
        base = c['size']
        rect = pymupdf.Rect(x0, y0 - 1.0, c['limit'], y1 + 1.0)
        size = base
        ok = False
        while size >= 4.5:
            # insert_textbox returns >=0 when the text fits
            rc = page.insert_textbox(rect, en, fontsize=size, fontname='helv',
                                     align=pymupdf.TEXT_ALIGN_LEFT, color=(0, 0, 0))
            if rc >= 0:
                ok = True
                break
            size -= 0.25
        if ok:
            stats['placed'] += 1
            if size < base - 0.24:
                stats['shrunk'] += 1
        else:
            # last resort: let it use the full width below the line, smallest size
            rect2 = pymupdf.Rect(x0, y0 - 1.0, max(c['limit'], x0 + 60), y1 + 8.0)
            if page.insert_textbox(rect2, en, fontsize=4.5, fontname='helv',
                                   align=pymupdf.TEXT_ALIGN_LEFT, color=(0, 0, 0)) >= 0:
                stats['placed'] += 1
                stats['shrunk'] += 1
            else:
                stats['failed'] += 1
                print('  could not place p%d: %s' % (pno, en[:60]))

doc.set_metadata({'title': 'DM-J3507-2EC Geared Motor User Manual V1.0 (unofficial English translation)',
                  'author': 'Shenzhen Damiao Technology Co., Ltd. (original)',
                  'subject': 'Machine-assisted English translation of the Chinese original; figures unchanged',
                  'keywords': 'DM-J3507-2EC DAMIAO actuator manual translation'})
doc.save(DST, garbage=3, deflate=True)
print('placed %d  (shrunk to fit %d)  failed %d' % (stats['placed'], stats['shrunk'], stats['failed']))
print('written:', DST, os.path.getsize(DST), 'bytes')
