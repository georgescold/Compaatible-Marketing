import sys
from pypdf import PdfReader

pdf_path = r"C:\Users\loysc\Desktop\Compaatible marketing\Knowledges\The Goal A Process Of Ongoing Improvement (Eliyahu M. Goldratt, Jeff Cox) (z-library.sk, 1lib.sk, z-lib.sk).pdf"

r = PdfReader(pdf_path)
total = len(r.pages)
print(f"TOTAL_PAGES:{total}")

# Extract all text
out_path = r"C:\Users\loysc\Desktop\Compaatible marketing\Knowledges\_goal_extracted.txt"
with open(out_path, "w", encoding="utf-8") as f:
    for i, page in enumerate(r.pages):
        try:
            t = page.extract_text() or ""
        except Exception as e:
            t = f"[ERR p{i+1}: {e}]"
        f.write(f"\n\n===== PAGE {i+1} =====\n\n")
        f.write(t)
print(f"OK_WROTE:{out_path}")
