from __future__ import annotations

from typing import Any

from lite_annotator.vocabulary import field_by_key, option_label


def extract_named_options(vocabulary: dict[str, Any], key: str) -> dict[str, str]:
    field = field_by_key(vocabulary, key)
    options = field.get("options") or {}
    return {
        str(value): str(label)
        for value, label in options.items()
    }


def object_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", "")).strip()
    return str(value or "").strip()


def object_color(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("color", "")).strip()
    return ""


def object_material(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("material", "")).strip()
    return ""


def object_ref(name: str, color: str = "", material: str = "") -> dict[str, str]:
    return {
        "name": str(name).strip(),
        "color": str(color).strip(),
        "material": str(material).strip(),
    }


def object_ref_text(value: Any) -> str:
    name = object_name(value)
    color = object_color(value)
    material = object_material(value)
    return " ".join(part for part in (color, material, name) if part)


def object_ref_matches(value: Any, text: str) -> bool:
    text = str(text).strip()
    if not text:
        return False
    return text in {
        object_name(value),
        object_ref_text(value),
    }


def object_display_label(
    value: Any,
    object_options: dict[str, str],
    color_options: dict[str, str] | None = None,
    material_options: dict[str, str] | None = None,
) -> str:
    name = object_name(value)
    color = object_color(value)
    material = object_material(value)
    object_label_text = object_options.get(name, name)
    parts = []
    if color:
        parts.append((color_options or {}).get(color, color))
    if material:
        parts.append((material_options or {}).get(material, material))
    parts.append(object_label_text)
    chinese_label = " ".join(part for part in parts if part)
    english_text = object_ref_text(value) or name
    return option_label(english_text, chinese_label)
