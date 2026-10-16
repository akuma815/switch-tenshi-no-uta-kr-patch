"""WBP_VisualSceneText의 RichTextBlock DefaultTextStyleOverride에 폰트 Size 필드를 주입한다.

배경:
  이 위젯의 자막 크기는 어떤 애셋 값으로도 조절되지 않았다. 원인은 RichTextBlock의
  DefaultTextStyleOverride(FTextBlockStyle, bOverrideDefaultStyle=true로 실사용 확인)에
  FSlateFontInfo.Size가 직렬화되어 있지 않아 엔진 기본 크기로 렌더되기 때문.
  unversioned 직렬화 fragment 헤더를 [FontObject][skip2, TypefaceFontName]에서
  [FontObject][skip2, TypefaceFontName+Size]로 바꾸고 float 4바이트를 삽입한다.

사용법:
  python inject_visualscene_fontsize.py <src_uexp> <src_uasset> <dst_uexp> <dst_uasset> <size>

원본(무패치) WBP_VisualSceneText.uexp/.uasset 전용. 구조 검증 실패 시 즉시 중단한다.
"""
import struct
import sys
from pathlib import Path

# ---- 원본 uexp 내 구조 오프셋 (실측 해독 결과) ----
FONTINFO_FRAG2 = 698     # FSlateFontInfo 2번째 fragment (0x0302 = skip2, value1, last)
INSERT_AT = 712          # TypefaceFontName 직후 = Size 삽입 위치
STYLE_HEADER = 694       # FTextBlockStyle fragment (0x0500 = value2, last)
TYPEFACE_FNAME = 704     # FName(Default) = 네임테이블 인덱스 2
OVERRIDE_FLAG = 730      # bOverrideDefaultStyle = 0x01

# ---- 원본 uasset export map (실측) ----
EXPORT0_SERIALOFFSET_POS = 3140  # export[0] SerialOffset(int64) 위치
EXPORT_STRIDE = 96
EXPORT_COUNT = 22
RICHTEXT_EXPORT_INDEX = 12       # RichTextBlock export (uexp 473..739)
UEXP_SIZE = 1187
UASSET_SIZE = 5733


def main():
    src_uexp, src_uasset, dst_uexp, dst_uasset, size = sys.argv[1:6]
    size = float(size)

    ux = bytearray(Path(src_uexp).read_bytes())
    ua = bytearray(Path(src_uasset).read_bytes())

    # ---- 구조 검증 ----
    if len(ux) != UEXP_SIZE or len(ua) != UASSET_SIZE:
        raise SystemExit(f"unexpected file sizes: uexp={len(ux)}, uasset={len(ua)}")
    if struct.unpack_from("<H", ux, STYLE_HEADER)[0] != 0x0500:
        raise SystemExit("FTextBlockStyle header != 0x0500")
    if struct.unpack_from("<H", ux, FONTINFO_FRAG2)[0] != 0x0302:
        raise SystemExit("FSlateFontInfo fragment2 != 0x0302")
    if struct.unpack_from("<ii", ux, TYPEFACE_FNAME) != (2, 0):
        raise SystemExit("TypefaceFontName FName != (2,0) 'Default'")
    if ux[OVERRIDE_FLAG] != 1:
        raise SystemExit("bOverrideDefaultStyle != true")

    # ---- uexp 패치 ----
    # fragment: skip=2, values=2(TypefaceFontName+Size), last -> (2<<9)|0x100|2 = 0x0502
    struct.pack_into("<H", ux, FONTINFO_FRAG2, 0x0502)
    ux[INSERT_AT:INSERT_AT] = struct.pack("<f", size)
    Path(dst_uexp).write_bytes(bytes(ux))

    # ---- uasset export map 보정 ----
    ss_pos = EXPORT0_SERIALOFFSET_POS - 8 + EXPORT_STRIDE * RICHTEXT_EXPORT_INDEX
    (ss,) = struct.unpack_from("<q", ua, ss_pos)
    if ss != 266:
        raise SystemExit(f"RichTextBlock SerialSize != 266 (found {ss})")
    struct.pack_into("<q", ua, ss_pos, ss + 4)
    for k in range(RICHTEXT_EXPORT_INDEX + 1, EXPORT_COUNT):
        so_pos = EXPORT0_SERIALOFFSET_POS + EXPORT_STRIDE * k
        (so,) = struct.unpack_from("<q", ua, so_pos)
        if not (UASSET_SIZE <= so < UASSET_SIZE + UEXP_SIZE):
            raise SystemExit(f"export[{k}] SerialOffset out of range: {so}")
        struct.pack_into("<q", ua, so_pos, so + 4)

    # BulkDataStartOffset(int64) = 헤더 + export 데이터 크기: 존재하면 +4
    bulk_old = UASSET_SIZE + UEXP_SIZE - 4  # 6916
    pat = struct.pack("<q", bulk_old)
    idx = ua.find(pat)
    while idx != -1:
        struct.pack_into("<q", ua, idx, bulk_old + 4)
        idx = ua.find(pat, idx + 1)

    Path(dst_uasset).write_bytes(bytes(ua))
    print(f"  injected FSlateFontInfo.Size = {size} (uexp {UEXP_SIZE} -> {len(ux)} bytes)")


if __name__ == "__main__":
    main()
