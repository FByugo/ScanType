#!/usr/bin/env python3
"""scantype.py: type out scanned pages and photos of printed text, and flag every line it is not sure of.

    scantype.py INPUT... --out DIR [--fields] [--min-conf 0.90]

INPUT is a PDF, an image (png, jpg, tif) or a folder of them. For each page it writes DIR/<name>.txt with the lines
in reading order, and it adds every line to DIR/review.csv with its confidence. A line under --min-conf is marked
CHECK so a person reads it against the page before the work goes back.

--fields also pulls invoice number, date, supplier and total from each file into DIR/fields.csv. A field it
cannot find is left blank and the remarks column says which one, instead of guessing.

Printed text only. Handwriting comes out with low confidence or wrong, so pages like that end up full of CHECK
lines and the summary says so. It does not claim to read them.

exit: 0 every line read with confidence at or over --min-conf · 1 some lines need a check · 2 bad input
"""
import argparse, csv, json, os, re, sys

IMG = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


def pages(path):
    """yield (label, image as BGR numpy array) for every page of every input."""
    import numpy as np, cv2, pymupdf
    if os.path.isdir(path):
        for n in sorted(os.listdir(path)):
            if n.lower().endswith(IMG + (".pdf",)):
                yield from pages(os.path.join(path, n))
        return
    base = os.path.splitext(os.path.basename(path))[0]
    if path.lower().endswith(".pdf"):
        doc = pymupdf.open(path)
        for i, pg in enumerate(doc, 1):
            pix = pg.get_pixmap(dpi=200)
            a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
            a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR) if pix.n >= 3 else cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
            yield "%s_p%d" % (base, i), base, i, a
    elif path.lower().endswith(IMG):
        a = cv2.imread(path)
        if a is None:
            raise ValueError("cannot read image " + path)
        yield base, base, 1, a


def views(img):
    """the second and third readings: enlarged 2x, and contrast boosted. Clean pages read the same in all three."""
    import cv2
    yield cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    yield cv2.cvtColor(cv2.createCLAHE(3.0, (8, 8)).apply(g), cv2.COLOR_GRAY2BGR)


def read(ocr, img):
    """[(text, confidence, agreed)] where agreed is True when the same line text comes back from another reading.
    2026-11-21: on a planted bad photocopy the engine read "Ref 55-0912-AQ" as "RH550912AO" with confidence 0.92, so
    confidence alone passed a wrong line. The other two readings gave "1550212A0" and "Red 55 0912.AQ"."""
    main = lines(ocr, img)
    other = set()
    for v in views(img):
        other |= {" ".join(t.split()) for t, _ in lines(ocr, v)}
    return [(t, c, " ".join(t.split()) in other) for t, c in main]


def lines(ocr, img):
    """OCR boxes grouped into lines, top to bottom then left to right."""
    r = ocr(img)
    boxes = []
    for b, text, conf in zip(r.boxes if r.boxes is not None else [], r.txts or [], r.scores or []):
        ys = [p[1] for p in b]; xs = [p[0] for p in b]
        boxes.append((sum(ys) / 4, min(xs), max(ys) - min(ys), text, float(conf)))
    boxes.sort()
    out = []
    for y, x, h, t, c in boxes:
        if out and abs(y - out[-1]["y"]) < 0.5 * max(h, out[-1]["h"]):
            out[-1]["parts"].append((x, t, c))
        else:
            out.append({"y": y, "h": h, "parts": [(x, t, c)]})
    res = []
    for l in out:
        parts = sorted(l["parts"])
        res.append((" ".join(p[1] for p in parts), min(p[2] for p in parts)))
    return res


DATE = r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2} (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* \d{4})\b"
FIELDS = {
    # the number must hold a digit and the label must end on a word boundary: "Tax Invoice" once gave the number "oice"
    "invoice_number": [r"\binv(oice)?\b\.?\s*(no|number|num|#)?\.?\s*[:#]?\s*((?=[A-Z/-]*\d)[A-Z0-9][A-Z0-9/-]{2,})"],
    "date": [r"\b(invoice )?date\b\s*[:]?\s*" + DATE, DATE],
    "supplier": [r"\b(supplier|vendor|from|seller|sold by)\s*[:]\s*(.+)"],
    "total": [r"\b(grand total|total amount|amount due|total due|total)\b\s*[:]?\s*[A-Z$€£₹]*\s*([0-9][0-9,]*\.\d{2})\b"],
}


def fields(text_lines):
    got, missing = {}, []
    for name, pats in FIELDS.items():
        val = ""
        for p in pats:
            for t, _ in text_lines:
                m = re.search(p, t, re.I)
                if m:
                    val = [g for g in m.groups() if g][-1].strip() if name != "date" else next(
                        g for g in m.groups() if g and re.search(r"\d", g))
                    break
            if val:
                break
        if name == "total" and not val:   # the last money amount on a line that says total, if the label and number split
            for t, _ in reversed(text_lines):
                if re.search(r"\btotal\b", t, re.I):
                    nums = re.findall(r"[0-9][0-9,]*\.\d{2}", t)
                    if nums:
                        val = nums[-1]
                        break
        got[name] = val
        if not val:
            missing.append(name)
    return got, missing


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fields", action="store_true")
    ap.add_argument("--min-conf", type=float, default=0.90)
    a = ap.parse_args(argv)
    for p in a.inputs:
        if not os.path.exists(p):
            print("no such input:", p, file=sys.stderr)
            return 2
    from rapidocr import RapidOCR   # rapidocr 3.x. 1.2.3 ran words together ("INVOICENo.KT-0093") on a planted scan
    ocr = RapidOCR(params={"Global.log_level": "error"})
    os.makedirs(a.out, exist_ok=True)
    review, per_file, summary = [], {}, {"pages": 0, "lines": 0, "check": 0, "empty_pages": []}
    for p in a.inputs:
        for label, base, num, img in pages(p):
            rd = read(ocr, img)
            ls = [(t, c) for t, c, _ in rd]
            summary["pages"] += 1
            if not ls:
                summary["empty_pages"].append(label)
            with open(os.path.join(a.out, label + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(t for t, _ in ls) + ("\n" if ls else ""))
            for i, (t, c, agreed) in enumerate(rd, 1):
                flag = "CHECK" if c < a.min_conf or not agreed else ""
                summary["lines"] += 1
                summary["check"] += bool(flag)
                review.append([label, i, "%.3f" % c, flag, t])
            per_file.setdefault(base, []).extend(ls)
    with open(os.path.join(a.out, "review.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["page", "line", "confidence", "flag", "text"]); w.writerows(review)
    if a.fields:
        with open(os.path.join(a.out, "fields.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["file"] + list(FIELDS) + ["remarks"])
            for base, ls in per_file.items():
                got, missing = fields(ls)
                low = [n for n in FIELDS if got[n] and any(got[n] in t and c < a.min_conf for t, c in ls)]
                rem = "; ".join(["not found: " + ", ".join(missing)] * bool(missing) + ["low confidence: " + ", ".join(low)] * bool(low))
                w.writerow([base] + [got[n] for n in FIELDS] + [rem])
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("%d pages, %d lines, %d to check, %d pages with no text%s" % (
        summary["pages"], summary["lines"], summary["check"], len(summary["empty_pages"]),
        "" if not summary["empty_pages"] else " (" + ", ".join(summary["empty_pages"]) + ")"))
    return 1 if summary["check"] or summary["empty_pages"] else 0


if __name__ == "__main__":
    sys.exit(main())
