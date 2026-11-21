"""builds planted scans: two invoices (one PDF of a scan, one PNG photo, noisy and tilted), one invoice with no total,
and one blank page. The truth for each goes to truth.json beside them."""
import json, os, sys
import numpy as np, cv2, pymupdf
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
INV = {
 "inv_a": ["INVOICE No. INV-20418", "Date: 14/03/2025", "Supplier: Harbor Steel Supply Ltd",
           "Steel bracket 40mm 12 3.75", "Hex bolts M8 box 30 41.20", "Total amount: 1,284.60"],
 "inv_b": ["Tax Invoice", "Invoice # BX-7731", "Invoice Date: 02/11/2025", "Vendor: Lakeside Paper Co",
           "A4 copy paper 10 reams 52.00", "Grand Total 118.45"],
 "inv_c": ["INVOICE No. KT-0093", "Date: 21/06/2025", "Supplier: North Field Farms", "Eggs 30 trays 96.00"],
}
FIELDS = {"inv_a": ["INV-20418", "14/03/2025", "Harbor Steel Supply Ltd", "1,284.60"],
          "inv_b": ["BX-7731", "02/11/2025", "Lakeside Paper Co", "118.45"],
          "inv_c": ["KT-0093", "21/06/2025", "North Field Farms", ""]}
def scan(lines, seed, angle):
    d = pymupdf.open(); p = d.new_page()
    for i, l in enumerate(lines): p.insert_text((72, 100 + 30 * i), l, fontsize=13)
    pix = p.get_pixmap(dpi=150)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].copy()
    M = cv2.getRotationMatrix2D((pix.w / 2, pix.h / 2), angle, 1)
    a = cv2.warpAffine(a, M, (pix.w, pix.h), borderValue=(255, 255, 255))
    a = np.clip(a.astype(int) + np.random.default_rng(seed).normal(0, 22, a.shape), 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(a, (3, 3), 0)
def as_pdf(img, path):   # a scanned PDF: an image and no text layer
    ok, png = cv2.imencode(".png", img); d = pymupdf.open(); p = d.new_page(width=612, height=792)
    p.insert_image(p.rect, stream=png.tobytes()); d.save(path)
as_pdf(scan(INV["inv_a"], 1, 1.5), os.path.join(out, "inv_a.pdf"))
cv2.imwrite(os.path.join(out, "inv_b.png"), scan(INV["inv_b"], 2, -2.0))
cv2.imwrite(os.path.join(out, "inv_c.jpg"), scan(INV["inv_c"], 3, 0.8))
cv2.imwrite(os.path.join(out, "blank.png"), np.full((1100, 850, 3), 250, np.uint8))
FAINT = ["Received 3 pallets from dock 7", "Signed by night shift lead", "Ref 55-0912-AQ"]
g = scan(FAINT, 4, 3.0)
g = cv2.resize(cv2.resize(g, None, fx=0.32, fy=0.32, interpolation=cv2.INTER_AREA), None, fx=1/0.32, fy=1/0.32)
g = np.clip(150 + (g.astype(int) - 150) * 0.35 + np.random.default_rng(5).normal(0, 30, g.shape), 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(out, "faint.png"), g)   # a bad photocopy: low contrast, low resolution, heavy noise
json.dump({"text": INV, "fields": FIELDS, "faint": FAINT}, open(os.path.join(out, "truth.json"), "w"), indent=1)
