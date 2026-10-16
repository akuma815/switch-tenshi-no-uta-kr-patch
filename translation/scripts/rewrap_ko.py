import csv
import sys

WRAP_WIDTH = 32.0

# 원문 레이아웃(전각 공백 정렬·고정 줄바꿈)을 그대로 보존해야 하는 행의 offset.
# 3844: 전투 커맨드 "어떻게 할까?(%s) / 공격 마법 도구 / 방어 도망치기" 3줄 메뉴
PRESERVE_LAYOUT_OFFSETS = {"3844"}

def char_width(ch):
    cp = ord(ch)
    if cp < 0x2000 or 0xFF61 <= cp <= 0xFF9F:
        return 0.5
    return 1.0

def text_width(s):
    return sum(char_width(c) for c in s)

def wrap_text(text, width=WRAP_WIDTH):
    # 원문(jp)의 줄바꿈 구조를 따르는 번역 시트의 줄바꿈을 그대로 보존한다.
    # (메뉴/선택지의 줄 단위 커서, 전각 공백 정렬이 줄바꿈에 의존한다)
    # 폭을 넘는 줄만 단어 단위로 추가 분할한다.
    normalized = text.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in normalized.split("\n"):
        out.extend(wrap_line(line, width))
    return "\n".join(out)

def wrap_line(flat, width=WRAP_WIDTH):
    if text_width(flat) <= width:
        return [flat]

    lines = []
    cur = ""
    cur_w = 0.0
    for word in flat.split(" "):
        w = text_width(word)
        add_w = w + (0.5 if cur else 0.0)
        if cur and cur_w + add_w > width:
            lines.append(cur)
            cur = ""
            cur_w = 0.0
            add_w = w
        # hard-break overlong single words
        while text_width(word) > width:
            take = ""
            tw = 0.0
            for ch in word:
                cw = char_width(ch)
                if tw + cw > width - cur_w - (0.5 if cur else 0.0):
                    break
                take += ch
                tw += cw
            if cur:
                lines.append(cur + " " + take if take else cur)
            else:
                lines.append(take)
            word = word[len(take):]
            cur = ""
            cur_w = 0.0
        if word:
            if cur:
                cur += " " + word
                cur_w += 0.5 + text_width(word)
            else:
                cur = word
                cur_w = text_width(word)
    if cur:
        lines.append(cur)
    return lines

def main():
    in_csv = sys.argv[1]
    out_csv = sys.argv[2]
    with open(in_csv, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    wrapped = 0
    over3 = 0
    for row in rows:
        ko = (row.get("ko") or "").strip()
        if not ko:
            continue
        if str(row.get("offset", "")) in PRESERVE_LAYOUT_OFFSETS:
            row["ko"] = ko.replace("\\n", "\n")
            continue
        new_ko = wrap_text(ko)
        if new_ko != ko:
            wrapped += 1
        row["ko"] = new_ko
        if new_ko.count("\n") + 1 > 3:
            over3 += 1

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    total_ko = sum(1 for r in rows if (r.get("ko") or "").strip())
    print(f"rows with ko: {total_ko}, rewrapped (changed): {wrapped}, entries exceeding 3 lines: {over3}")

if __name__ == "__main__":
    main()
