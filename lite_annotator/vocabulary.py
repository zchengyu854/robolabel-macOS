from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lite_annotator.paths import resource_path

DEFAULT_VOCABULARY_PATH = resource_path("config/lite_vocabulary.json")


def load_vocabulary(path: str | Path = DEFAULT_VOCABULARY_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"fields": []}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def field_by_key(vocabulary: dict[str, Any], key: str) -> dict[str, Any]:
    for field in vocabulary.get("fields", []):
        if field.get("key") == key:
            return field
    return {}


def sorted_options(options: dict[str, str]) -> dict[str, str]:
    return {
        key: options[key]
        for key in sorted(options, key=lambda item: str(options[item]))
    }


def extract_space_options(vocabulary: dict[str, Any]) -> dict[str, str]:
    field = field_by_key(vocabulary, "scene_level2")
    options = {}
    for nested_options in (field.get("options_map") or {}).values():
        options.update(nested_options or {})
    return sorted_options(options)


def extract_object_options(vocabulary: dict[str, Any]) -> dict[str, str]:
    field = field_by_key(vocabulary, "objects")
    return sorted_options(field.get("name_options") or {})


def option_label(value: str, label: str) -> str:
    return f"{label}({value})"


def value_from_option_text(text: str, options: dict[str, str]) -> str:
    text = str(text).strip()
    if text in options:
        return text
    for value, label in options.items():
        if text == str(label).strip() or text == option_label(value, label):
            return value
    if text.endswith(")") and "(" in text:
        candidate = text.rsplit("(", 1)[1][:-1].strip()
        if candidate in options:
            return candidate
    return text
