"""uexp의 지정 오프셋에 있는 float32 값을 검증 후 교체한다.

사용법:
  python patch_floats_at_offsets.py <src_uexp> <dst_uexp> <offset:old:new> [<offset:old:new> ...]

전역 바이트 패턴 치환(patch_richtext_font_size.py)과 달리 오프셋을 직접 지정하므로
문자열 등 다른 데이터에 걸친 우연한 패턴을 건드릴 위험이 없다.
"""
import struct
import sys
from pathlib import Path


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = bytearray(Path(src).read_bytes())
    for spec in sys.argv[3:]:
        off_s, old_s, new_s = spec.split(":")
        off, old, new = int(off_s), float(old_s), float(new_s)
        (cur,) = struct.unpack_from("<f", data, off)
        if abs(cur - old) > 1e-4:
            raise SystemExit(f"offset {off}: expected {old}, found {cur}")
        struct.pack_into("<f", data, off, new)
        print(f"  offset {off}: {old} -> {new}")
    Path(dst).write_bytes(bytes(data))


if __name__ == "__main__":
    main()
