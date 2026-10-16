"""임의 XLSX -> CSV 변환 (컬럼 그대로, 숫자 셀은 정수로 정규화)

사용법: python xlsx2csv_any.py <입력.xlsx> <출력.csv>
"""
import csv
import sys

from openpyxl import load_workbook

in_xlsx = sys.argv[1]
out_csv = sys.argv[2]

wb = load_workbook(in_xlsx, read_only=True)
ws = wb.active

def norm(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    # Excel의 OOXML 제어문자 이스케이프 복원 (_x000D_ = \r)
    return str(v).replace("_x000D_", "\r")

rows = []
header = None
for r in ws.iter_rows(values_only=True):
    if header is None:
        header = [norm(c) for c in r]
        continue
    rows.append([norm(c) for c in r])
wb.close()

with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
print(f"{out_csv}: {len(rows)} rows")
