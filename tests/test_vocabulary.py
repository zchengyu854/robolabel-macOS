from __future__ import annotations

from lite_annotator.vocabulary import extract_object_options, load_vocabulary


def test_object_vocabulary_includes_common_robot_task_objects_and_corrected_aliases():
    objects = extract_object_options(load_vocabulary())

    for key in [
        "rubber ball",
        "egg whisk",
        "kitchen sink",
        "eyeglass case",
        "trash bin",
        "water-based marker",
        "wooden block",
        "workspace",
        "button",
        "drawer handle",
        "sponge brush",
        "screwdriver",
        "person",
    ]:
        assert key in objects

    assert objects["mangosteen"] == "山竹"
    assert objects["person"] == "人/接收人"

    for legacy_key in [
        "ruban ball",
        "egg-whisk",
        "washing-up sink",
        "glasses box",
        "dustbin",
        "deli water-based marker",
        "Instant drip coffee bags",
        "canned Fig",
        "Slippers",
    ]:
        assert legacy_key not in objects
