# -*- coding: utf-8 -*-
import json
import struct
import sys


def trim_to_utf8_bytes(text, max_bytes):
    out = ""
    used = 0
    for ch in text:
        b = ch.encode("utf-8")
        if used + len(b) > max_bytes:
            break
        out += ch
        used += len(b)
    return out, used


def encode_fixed_utf8(text, total_size):
    # Positive UE FString length. Keep the serialized field exactly total_size bytes
    # so every following visual-scene text offset stays identical to the original.
    payload_size = total_size - 4
    if payload_size <= 0:
        raise ValueError(f"invalid FString slot size: {total_size}")

    max_text_bytes = payload_size - 1
    visible, used = trim_to_utf8_bytes(text, max_text_bytes)
    pad = b" " * (max_text_bytes - used)
    payload = visible.encode("utf-8") + pad + b"\x00"
    if len(payload) != payload_size:
        raise AssertionError((len(payload), payload_size))
    return struct.pack("<i", payload_size) + payload, visible


def old_total_size(repl):
    enc = repl["old_encoding"]
    length_field = repl["old_length_field"]
    if enc == "ascii":
        return 4 + length_field
    return 4 + (-length_field) * 2


def apply(uexp_path, repl_json, out_path):
    with open(uexp_path, "rb") as f:
        data = bytearray(f.read())
    with open(repl_json, "r", encoding="utf-8") as f:
        replacements = json.load(f)

    truncated = 0
    for repl in replacements:
        off = repl["offset"]
        total = old_total_size(repl)
        old = bytes(data[off:off + total])
        if len(old) != total:
            raise ValueError(f"replacement outside file at {off}")
        encoded, visible = encode_fixed_utf8(repl["new_text"].rstrip(" \u3000\u200b"), total)
        if visible != repl["new_text"].rstrip(" \u3000\u200b"):
            truncated += 1
        data[off:off + total] = encoded

    with open(out_path, "wb") as f:
        f.write(data)
    print(f"fixed-slot visualscene replacements: {len(replacements)}, truncated: {truncated}, size unchanged: {len(data)}")


if __name__ == "__main__":
    apply(sys.argv[1], sys.argv[2], sys.argv[3])
