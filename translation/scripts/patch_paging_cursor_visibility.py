"""WBP_Paging의 페이지 진행 아이콘을 Hidden 상태로 고정한다.

텍스처를 패치 컨테이너에 추가하지 않는다. 기존 WBP_Paging 바이트코드에 있는
SetVisibility(Visible) 호출의 ESlateVisibility 인수만 Hidden으로 바꾼다.

사용법:
  python patch_paging_cursor_visibility.py <src_uexp> <src_uasset> <dst_uexp> <dst_uasset>
"""
import struct
import sys
from pathlib import Path


VISIBLE = 0
HIDDEN = 2
EXPECTED_VISIBLE_CALLS = 2
EXPECTED_UEXP_SIZE = 2163
EXPECTED_UASSET_SIZE = 4500


def name_index(data: bytes, name: str) -> int:
    """원본 WBP_Paging의 FName 맵에서 이름 인덱스를 찾는다."""
    marker = name.encode("ascii") + b"\0"
    pos = data.find(marker)
    if pos < 4:
        raise SystemExit(f"FName not found: {name}")
    (length,) = struct.unpack_from("<i", data, pos - 4)
    if length != len(marker):
        raise SystemExit(f"unexpected FName layout: {name}")

    first = data.find(b"BlueprintType\0") - 4
    index = 0
    cursor = first
    while cursor < pos - 4:
        (entry_len,) = struct.unpack_from("<i", data, cursor)
        if entry_len <= 0:
            raise SystemExit("invalid FName map entry")
        cursor += 4 + entry_len + 4
        index += 1
    if cursor != pos - 4:
        raise SystemExit("failed to align FName map")
    return index


def main() -> None:
    src_uexp, src_uasset, dst_uexp, dst_uasset = map(Path, sys.argv[1:5])
    uexp = bytearray(src_uexp.read_bytes())
    uasset = src_uasset.read_bytes()

    if len(uexp) != EXPECTED_UEXP_SIZE or len(uasset) != EXPECTED_UASSET_SIZE:
        raise SystemExit(
            f"unexpected WBP_Paging sizes: uexp={len(uexp)}, uasset={len(uasset)}"
        )

    set_visibility = name_index(uasset, "SetVisibility")
    before = b"\x1b" + struct.pack("<ii", set_visibility, 0) + bytes([0x24, VISIBLE, 0x16])
    after = b"\x1b" + struct.pack("<ii", set_visibility, 0) + bytes([0x24, HIDDEN, 0x16])
    count = uexp.count(before)
    if count != EXPECTED_VISIBLE_CALLS:
        raise SystemExit(
            f"expected {EXPECTED_VISIBLE_CALLS} SetVisibility(Visible) calls, found {count}"
        )
    if HIDDEN == VISIBLE:
        raise SystemExit("visibility constants are invalid")

    uexp = bytearray(uexp.replace(before, after))
    if len(uexp) != EXPECTED_UEXP_SIZE:
        raise SystemExit("uexp length changed")

    dst_uexp.parent.mkdir(parents=True, exist_ok=True)
    dst_uexp.write_bytes(uexp)
    dst_uasset.write_bytes(uasset)
    print(f"  WBP_Paging: SetVisibility Visible -> Hidden ({count} calls, size unchanged)")


if __name__ == "__main__":
    main()
