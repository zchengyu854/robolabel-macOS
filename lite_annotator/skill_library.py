from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from common.skill_schema import load_skill_templates
from lite_annotator.vocabulary import option_label


_, SKILL_TEMPLATES = load_skill_templates()


def skill_library_path(dataset_root: str | Path) -> Path:
    return Path(dataset_root) / "lite_annotations" / "skill_descriptions.json"


def empty_skill_library() -> dict[str, Any]:
    return {"version": 1, "skills": []}


def load_skill_library(dataset_root: str | Path) -> dict[str, Any]:
    path = skill_library_path(dataset_root)
    if not path.exists():
        return empty_skill_library()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", 1)
    data.setdefault("skills", [])
    return data


def save_skill_library(dataset_root: str | Path, library: dict[str, Any]) -> None:
    path = skill_library_path(dataset_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)


def next_skill_id(skills: list[dict[str, Any]]) -> str:
    max_number = 0
    for skill in skills:
        raw_id = str(skill.get("id", ""))
        if raw_id.startswith("skill_"):
            try:
                max_number = max(max_number, int(raw_id.split("_", 1)[1]))
            except ValueError:
                continue
    return f"skill_{max_number + 1:06d}"


def add_skill_template(dataset_root: str | Path, template: dict[str, Any]) -> dict[str, Any]:
    library = load_skill_library(dataset_root)
    item = {
        "id": next_skill_id(library["skills"]),
        "text": str(template.get("text", "")).strip(),
        "template": template,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    library["skills"].append(item)
    save_skill_library(dataset_root, library)
    return item


def delete_skill_template(dataset_root: str | Path, skill_id: str) -> None:
    library = load_skill_library(dataset_root)
    library["skills"] = [
        item for item in library["skills"]
        if item.get("id") != skill_id
    ]
    save_skill_library(dataset_root, library)


def skill_display_hint(item: dict[str, Any]) -> str:
    template = item.get("template") or item
    actions = template.get("actions") or []
    labels = []
    for action in actions:
        skill_id = str(action.get("skill", "")).strip()
        if not skill_id:
            continue
        display_name = SKILL_TEMPLATES.get(skill_id, {}).get("display_name", skill_id)
        label = option_label(skill_id, display_name)
        if label not in labels:
            labels.append(label)
    return "+".join(labels)


def skill_display_text(item: dict[str, Any]) -> str:
    text = str(item.get("text", "") or item.get("id", "")).strip()
    hint = skill_display_hint(item)
    if hint and text:
        return f"{hint}  {text}"
    return hint or text
