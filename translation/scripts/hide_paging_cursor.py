"""대화창 페이징 커서(삼각형) 숨김: message_button 텍스처를 완전 투명 DXT5로 만든다.

WBP_Paging의 삼각형 커서는 8x8 DXT5 텍스처(message_button1/2)를 그린 것이며,
위치는 네이티브 코드가 고정해 위젯 측 조정이 불가능하다. 텍스처의 모든 밉 페이로드를
0으로 채우면 DXT5 알파가 전부 0이 되어 완전 투명해진다(형상 자체가 사라짐).

페이로드 바이트 수를 그대로 유지하므로 uexp 길이·SerialSize가 변하지 않는다
(uasset은 그대로 복사). 밉 헤더/치수/GUID 등 픽셀 외 데이터는 건드리지 않는다.

사용법:
  python hide_paging_cursor.py <src_uexp> <src_uasset> <dst_uexp> <dst_uasset>
"""
import struct
import sys
from pathlib import Path


def dxt5_size(w, h):
    return ((w + 3) // 4) * ((h + 3) // 4) * 16


def transparentize(ux):
    ux = bytearray(ux)
    if ux[-4:] != b"\xc1\x83\x2a\x9e":
        raise SystemExit("missing PACKAGE_FILE_TAG")
    fi = ux.find(b"PF_DXT5")
    if fi < 0:
        raise SystemExit("PF_DXT5 not found (unexpected format)")
    search_from = fi + len(b"PF_DXT5")
    total = 0
    for (w, h) in [(8, 8), (4, 4), (2, 2), (1, 1)]:
        marker = struct.pack("<iii", w, h, 1)
        idx = ux.find(marker, search_from)
        if idx < 0:
            raise SystemExit(f"mip {w}x{h} dims marker not found")
        psize = dxt5_size(w, h)
        pstart = idx - psize
        # 페이로드 구간을 0으로 (DXT5 16바이트 블록이 전부 0 -> 알파 0 = 완전 투명)
        for i in range(pstart, idx):
            ux[i] = 0
        total += psize
        search_from = idx + 12
    return bytes(ux), total


def main():
    src_uexp, src_uasset, dst_uexp, dst_uasset = sys.argv[1:5]
    orig = Path(src_uexp).read_bytes()
    out, changed = transparentize(orig)
    if len(out) != len(orig):
        raise SystemExit("length changed (must stay identical)")
    Path(dst_uexp).write_bytes(out)
    Path(dst_uasset).write_bytes(Path(src_uasset).read_bytes())
    print(f"  transparentized {changed} payload bytes ({len(orig)} bytes total, length unchanged)")


if __name__ == "__main__":
    main()
