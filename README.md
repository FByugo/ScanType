# ScanType

Types out scanned pages and photos of printed text, and marks every line it is not sure of so a person checks that line against the page before the work goes back.

Each page is read three times: as it is, enlarged, and with the contrast boosted. A clean page reads the same all three times. A line that comes back different, or with a low score from the OCR engine, gets marked CHECK in review.csv. The score alone is not enough. On a bad photocopy in the tests the engine read "Ref 55-0912-AQ" as "RH550912AO" and still scored it 0.92.

With --fields it also pulls invoice number, date, supplier and total from each file into fields.csv. A field it cannot find is left blank and the remarks column names it, so nothing gets guessed.

## Use

    pip install rapidocr onnxruntime pymupdf
    python3 scantype.py scans/ --out typed/ --fields

Input can be PDFs of scans, images (png, jpg, tif) or a folder. Output per page is a .txt, plus review.csv, fields.csv and summary.json. Exit code 1 means some lines need a check or a page had no text.

## Known limits

Printed text only. Handwriting comes out wrong or full of CHECK lines and it does not pretend otherwise. Tried on planted scans only so far (tilted, noisy, blurred, one bad photocopy and one blank page), not yet on a real client's batch.

## Test

    bash check.sh

Builds the planted scans, runs the tool and compares every page with the text it was made from. Five broken copies of the tool are run too (one that guesses a missing total, one that never marks CHECK, one that trusts the score alone, one that hides a blank page, one that reads lines bottom up) and every one of them has to fail.
