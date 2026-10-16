import json
import csv
import sys

def looks_like_hex_key(s):
    return len(s) >= 4 and all(c in "0123456789ABCDEFabcdef" for c in s)

def regen_tenshi_rows(strings_json):
    with open(strings_json, "r", encoding="utf-8") as f:
        items = json.load(f)
    rows = []
    i = 0
    n = len(items)
    while i < n:
        it = items[i]
        if it["encoding"] == "ascii" and looks_like_hex_key(it["text"]):
            key_item = it
            i += 1
            jp_item = None
            en_item = None
            if i < n and items[i]["encoding"] == "utf16":
                jp_item = items[i]
                i += 1
            if i < n and items[i]["encoding"] in ("ascii", "utf16"):
                nxt = items[i]
                if not (nxt["encoding"] == "ascii" and looks_like_hex_key(nxt["text"])):
                    en_item = nxt
                    i += 1
            rows.append({"key": key_item, "jp": jp_item, "en": en_item})
            continue
        i += 1
    return rows

def regen_visualscene_rows(strings_json):
    with open(strings_json, "r", encoding="utf-8") as f:
        items = json.load(f)

    def has_cjk(s, ignore_ideographic_space=False):
        # en 판정 시 전각 공백(U+3000)은 CJK로 치지 않는다.
        # 엔딩 크레딧의 영문(utf16)에 전각 공백이 섞여 있어 쌍 생성이 누락됐었다.
        for c in s:
            o = ord(c)
            if o == 0x3000 and ignore_ideographic_space:
                continue
            if 0x3000 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7A3:
                return True
        return False

    rows = []
    paired = set()
    i = 0
    n = len(items)
    while i < n - 1:
        a = items[i]
        b = items[i + 1]
        if has_cjk(a["text"]) and not has_cjk(b["text"], True) and len(b["text"]) >= 1:
            rows.append({"jp": a, "en": b})
            paired.add(a["offset"])
            paired.add(b["offset"])
            i += 2
            continue
        i += 1
    # 짝 없는 영문 고아 문자열 (예: 일문 코멘트 1개가 영문 2개로 분할된 뒷부분)
    for it in items:
        if it["offset"] not in paired and not has_cjk(it["text"], True) and len(it["text"]) >= 20:
            rows.append({"jp": None, "en": it})
    return rows

def main():
    mode = sys.argv[1]  # "tenshi" or "visualscene"
    strings_json = sys.argv[2]
    ko_csv = sys.argv[3]
    out_json = sys.argv[4]

    if mode == "tenshi":
        regen = regen_tenshi_rows(strings_json)
    else:
        regen = regen_visualscene_rows(strings_json)

    with open(ko_csv, "r", encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.DictReader(f))

    if len(regen) != len(csv_rows):
        print(f"WARNING: row count mismatch: regen={len(regen)} csv={len(csv_rows)}")

    replacements = []
    mismatches = 0
    # offset 기준 매칭 (행 순서 무관):
    #  - visualscene: csv offset = jp 문자열 offset (jp 없는 고아 행은 en offset)
    #  - tenshi: csv offset = key(hex 키) 문자열 offset
    # 시트가 재정렬되어도 인덱스 어긋남이 발생하지 않는다.
    if mode == "visualscene":
        def regen_key(r):
            return r["jp"]["offset"] if r.get("jp") else r["en"]["offset"]
    else:
        def regen_key(r):
            return r["key"]["offset"]
    regen_by_offset = {regen_key(r): r for r in regen}
    pairs = []
    for c in csv_rows:
        try:
            key = int(c.get("offset", ""))
        except ValueError:
            mismatches += 1
            continue
        r = regen_by_offset.get(key)
        if r is None:
            mismatches += 1
            continue
        pairs.append((r, c))

    for r, c in pairs:
        en_item = r.get("en")
        raw_ko = c.get("ko", "")
        if mode == "visualscene":
            ko = raw_ko.rstrip("\r\n")
        else:
            ko = raw_ko.strip()
        if not ko.strip():
            continue
        if en_item is None:
            mismatches += 1
            continue
        # sanity check text matches (allow the csv's en field to match)
        csv_en = c.get("en", "")
        if csv_en != en_item["text"]:
            mismatches += 1
            continue
        replacements.append({
            "offset": en_item["offset"],
            "old_encoding": en_item["encoding"],
            "old_length_field": en_item["length_field"],
            "old_text": en_item["text"],
            "new_text": ko,
        })

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(replacements, f, ensure_ascii=False, indent=1)

    print(f"regen rows: {len(regen)}, csv rows: {len(csv_rows)}, mismatches: {mismatches}")
    print(f"replacements built: {len(replacements)}")

if __name__ == "__main__":
    main()
