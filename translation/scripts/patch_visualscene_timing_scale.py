import json
import struct
import sys
from pathlib import Path


def string_total_size(item):
    n = item["length_field"]
    if item["encoding"] == "ascii":
        return 4 + n
    return 4 + (-n) * 2


def patch_timing(uexp_path, strings_json, scale, out_path):
    data = bytearray(Path(uexp_path).read_bytes())
    items = json.loads(Path(strings_json).read_text(encoding="utf-8"))

    patched = 0
    # The visual-scene table is serialized as JP text + EN text + a small row
    # metadata block. In that block, +12 is the cue time; +16 is an optional
    # end time for rows that have one.
    for pair in range(0, len(items) - 1, 2):
        en = items[pair + 1]
        end_en = en["offset"] + string_total_size(en)
        next_off = items[pair + 2]["offset"] if pair + 2 < len(items) else len(data)
        meta_len = next_off - end_en
        if meta_len < 16:
            continue

        cue_off = end_en + 12
        cue = struct.unpack_from("<f", data, cue_off)[0]
        if 0.0 < cue < 1000.0:
            struct.pack_into("<f", data, cue_off, cue * scale)
            patched += 1

        if meta_len >= 20:
            end_off = end_en + 16
            end_time = struct.unpack_from("<f", data, end_off)[0]
            if cue < end_time < 1000.0:
                struct.pack_into("<f", data, end_off, end_time * scale)
                patched += 1

    Path(out_path).write_bytes(data)
    print(f"visualscene timing scaled: x{scale:g}, patched floats: {patched}")


if __name__ == "__main__":
    patch_timing(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4])
