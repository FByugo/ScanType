#!/usr/bin/env bash
# planted case test for scantype.py. Exit 1 on any failure. Also runs broken copies that must fail.
cd "$(dirname "$0")/.." || exit 2
PY=${SCANTYPE_PY:-$HOME/.ocr/venv/bin/python}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
"$PY" tests/make_fixture.py "$T/in" || exit 2
judge() {   # $1 tool file, prints the failures, returns their count
  "$PY" "$1" "$T/in" --out "$T/out" --fields > "$T/stdout" 2>&1; rc=$?
  "$PY" - "$T" "$rc" <<'PYEOF'
import csv, difflib, json, os, sys
T, rc = sys.argv[1], int(sys.argv[2]); fails = []
truth = json.load(open(os.path.join(T, "in", "truth.json")))
names = {"inv_a": "inv_a_p1", "inv_b": "inv_b", "inv_c": "inv_c"}
for k, label in names.items():
    p = os.path.join(T, "out", label + ".txt")
    got = open(p).read().split() if os.path.exists(p) else []
    r = difflib.SequenceMatcher(None, " ".join(truth["text"][k]).split(), got).ratio()
    if r < 0.97: fails.append("%s words matched %.3f, need 0.97" % (k, r))
rows = {r["file"]: r for r in csv.DictReader(open(os.path.join(T, "out", "fields.csv")))} if os.path.exists(os.path.join(T, "out", "fields.csv")) else {}
for k, want in truth["fields"].items():
    r = rows.get(k)
    if not r: fails.append(k + " has no fields row"); continue
    got = [r["invoice_number"], r["date"], r["supplier"], r["total"]]
    if got != want: fails.append("%s fields %s, want %s" % (k, got, want))
if "inv_c" in rows and "not found: total" not in rows["inv_c"]["remarks"]: fails.append("inv_c remarks do not name the missing total")
s = json.load(open(os.path.join(T, "out", "summary.json"))) if os.path.exists(os.path.join(T, "out", "summary.json")) else {}
import csv as _c
faint = [r for r in _c.DictReader(open(os.path.join(T, "out", "review.csv")))] if os.path.exists(os.path.join(T, "out", "review.csv")) else []
fl = [r for r in faint if r["page"] == "faint"]
for r in fl:   # every line not word for word on the page must be marked CHECK
    if " ".join(r["text"].split()) not in truth["faint"] and r["flag"] != "CHECK":
        fails.append("faint line read wrong and not marked CHECK: " + r["text"])
if not fl: fails.append("the faint page has no rows")
if "blank" not in s.get("empty_pages", []): fails.append("the blank page is not named")
if rc != 1: fails.append("exit %d, want 1 because a page is blank" % rc)
for f in fails: print("  FAIL", f)
sys.exit(min(len(fails), 100))
PYEOF
}
judge scantype.py; n=$?
[ $n -eq 0 ] && echo "PASS real tool" || { echo "FAIL real tool, $n failures"; cat "$T/stdout"; }
bad=0
mut() {   # $1 name, $2 python replace old, $3 new
  "$PY" -c "import sys;s=open('scantype.py').read();o,n=sys.argv[1],sys.argv[2];assert o in s,o;open(sys.argv[3],'w').write(s.replace(o,n))" "$2" "$3" "$T/m.py" || { echo "mutant $1 did not apply"; bad=1; return; }
  rm -rf "$T/out"; judge "$T/m.py" >/dev/null; m=$?
  [ $m -gt 0 ] && echo "PASS mutant $1 fails ($m)" || { echo "FAIL mutant $1 passed"; bad=1; }
}
mut guesses_total 'got[name] = val' 'got[name] = val or (re.findall(r"[0-9][0-9,]*\.\d{2}", " ".join(t for t, _ in text_lines)) or [""])[-1]'
mut no_check 'flag = "CHECK" if c < a.min_conf or not agreed else ""' 'flag = ""'
mut conf_only 'flag = "CHECK" if c < a.min_conf or not agreed else ""' 'flag = "CHECK" if c < a.min_conf else ""'
mut hides_blank 'summary["empty_pages"].append(label)' 'pass'
mut wrong_order 'boxes.sort()' 'boxes.sort(reverse=True)'
[ $n -eq 0 ] && [ $bad -eq 0 ] && exit 0 || exit 1
