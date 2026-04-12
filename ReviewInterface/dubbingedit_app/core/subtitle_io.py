from __future__ import annotations

from typing import Any


def write_merged_subtitle(path: str, subtitles: list[dict[str, Any]], roles: list[str]) -> None:
    """按解析器可读的块格式写回 UTF-8-BOM。"""
    parts: list[str] = []
    for i, sub in enumerate(subtitles):
        role = roles[i] if i < len(roles) and roles else "default"
        parts.append(str(sub["index"]))
        parts.append(f"{sub['start']} --> {sub['end']}")
        parts.append(f"{role}: {sub['text']}")
        parts.append("")
    text = "\n".join(parts).rstrip() + "\n"
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(text)
