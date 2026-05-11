from __future__ import annotations

from pathlib import Path
import re


MAX_FILENAME_BYTES = 255


def normalize_original_name(filename: str, default_name: str) -> str:
    name = Path(filename or "").name.strip()
    return name or default_name


def safe_stem(value: str, default_stem: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe_value or default_stem


def clamp_filename_bytes(filename: str, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    if len(filename.encode("utf-8")) <= max_bytes:
        return filename

    suffix = Path(filename).suffix
    stem = filename[: -len(suffix)] if suffix else filename
    suffix_bytes = len(suffix.encode("utf-8"))
    stem_budget = max_bytes - suffix_bytes

    if stem_budget <= 0:
        truncated = filename.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        return truncated or "arquivo"

    while stem and len(stem.encode("utf-8")) > stem_budget:
        stem = stem[:-1]

    stem = stem.rstrip("._-") or "arquivo"
    return f"{stem}{suffix}"


def build_safe_filename(
    original_name: str,
    *,
    prefix: str | None = None,
    default_stem: str = "arquivo",
    default_suffix: str = "",
    max_bytes: int = MAX_FILENAME_BYTES,
) -> str:
    fallback_name = f"{default_stem}{default_suffix}"
    normalized_name = normalize_original_name(original_name, fallback_name)

    suffix = Path(normalized_name).suffix.lower()
    if not suffix and default_suffix:
        suffix = default_suffix

    stem = safe_stem(Path(normalized_name).stem, default_stem)
    safe_prefix = safe_stem(prefix, default_stem) if prefix else ""
    if safe_prefix:
        composed = f"{safe_prefix}_{stem}{suffix}"
    else:
        composed = f"{stem}{suffix}"

    return clamp_filename_bytes(composed, max_bytes=max_bytes)
