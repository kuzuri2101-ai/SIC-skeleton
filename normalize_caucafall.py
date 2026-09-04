"""Build a clean, reproducible CAUCAFall dataset without modifying raw data.

The processed image files are hard links to the originals, so the normalized
directory layout does not duplicate the roughly 8 GB image collection.
Image resizing and pixel standardization are intentionally loader-time steps.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path


ACTIVITY_NAMES = {
    "Fall backwards": "fall_backward",
    "Fall forward": "fall_forward",
    "Fall left": "fall_left",
    "Fall right": "fall_right",
    "Fall sitting": "fall_sitting",
    "Hop": "hop",
    "Kneel": "kneel",
    "Pick up object": "pick_up_object",
    "Sit down": "sit_down",
    "Walk": "walk",
}

SPLITS = {
    1: "train", 2: "train", 3: "train", 4: "train",
    5: "train", 6: "train", 7: "train",
    8: "validation",
    9: "test", 10: "test",
}

LIGHTING = {
    1: ("natural", 210), 2: ("natural", 203),
    3: ("natural", 218), 4: ("natural", 221),
    5: ("artificial", 127), 6: ("zero_lux", 0),
    7: ("artificial", 125), 8: ("zero_lux", 0),
    9: ("artificial", 128), 10: ("artificial", 130),
}

# Dataset naming defects verified against the full file inventory.
LABEL_OVERRIDES = {
    (2, "Fall backwards", "cas200091 - copia"): "cas200091.txt",
    (8, "Hop", "sals800096"): "sals800096a.txt",
    (8, "Pick up object", "res800090"): "res800090a.txt",
    (9, "Walk", "cams900140"): "cams900140w.txt",
}

CSV_FIELDS = [
    "sample_id", "image_path", "label_path", "subject_id", "activity",
    "video_id", "frame_index", "class_id", "class_name", "lighting",
    "lux", "width", "height", "split", "source_image", "source_label",
]


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def parse_label(path: Path) -> tuple[int, tuple[float, float, float, float]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"expected exactly one non-empty row, got {len(lines)}")
    fields = lines[0].split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {len(fields)}")
    class_id = int(fields[0])
    box = tuple(float(value) for value in fields[1:])
    if class_id not in (0, 1):
        raise ValueError(f"invalid class id {class_id}")
    if not all(0.0 <= value <= 1.0 for value in box):
        raise ValueError("box value outside [0, 1]")
    x, y, width, height = box
    if width <= 0.0 or height <= 0.0:
        raise ValueError("box width and height must be positive")
    if x - width / 2 < -1e-6 or x + width / 2 > 1.0 + 1e-6:
        raise ValueError("box exceeds horizontal image bounds")
    if y - height / 2 < -1e-6 or y + height / 2 > 1.0 + 1e-6:
        raise ValueError("box exceeds vertical image bounds")
    return class_id, box


def frame_index(stem: str, subject_id: int) -> int:
    groups = re.findall(r"\d+", stem)
    if not groups:
        raise ValueError("filename has no trailing frame number")
    digits = groups[-1]
    subject = str(subject_id)
    # Most names concatenate subject ID with a six-digit frame field, while
    # the cfs names separate the two with a hyphen.
    if len(groups) == 1 and digits.startswith(subject) and len(digits) > len(subject):
        digits = digits[len(subject):]
    return int(digits)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def link_image(source: Path, destination: Path) -> None:
    if destination.exists():
        source_stat = source.stat()
        destination_stat = destination.stat()
        if (source_stat.st_dev, source_stat.st_ino) != (
            destination_stat.st_dev, destination_stat.st_ino
        ):
            raise FileExistsError(f"destination is not the expected hard link: {destination}")
        return
    os.link(source, destination)


def normalize(raw_root: Path, output_root: Path) -> None:
    raw_root = raw_root.resolve()
    output_root = output_root.resolve()
    if not raw_root.is_dir():
        raise FileNotFoundError(raw_root)

    for split in ("train", "validation", "test"):
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    manifests = output_root / "manifests"
    reports = output_root / "reports"
    manifests.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    rows_by_split: dict[str, list[dict[str, object]]] = defaultdict(list)
    problems: list[dict[str, str]] = []
    source_labels_used: set[Path] = set()
    activity_counts: Counter[tuple[str, str]] = Counter()
    class_counts: Counter[tuple[str, str]] = Counter()
    subject_counts: Counter[tuple[str, int]] = Counter()
    dimensions: Counter[tuple[int, int]] = Counter()
    rename_rows: list[dict[str, str]] = []

    subject_dirs = sorted(raw_root.glob("Subject.*"), key=lambda p: int(p.name.split(".")[1]))
    for subject_dir in subject_dirs:
        subject_id = int(subject_dir.name.split(".")[1])
        split = SPLITS[subject_id]
        lighting, lux = LIGHTING[subject_id]
        for activity_dir in sorted(subject_dir.iterdir()):
            if not activity_dir.is_dir() or activity_dir.name not in ACTIVITY_NAMES:
                continue
            activity = ACTIVITY_NAMES[activity_dir.name]
            video_files = list(activity_dir.glob("*.avi"))
            video_id = video_files[0].stem if video_files else f"{activity}_s{subject_id:02d}"
            for image in sorted(activity_dir.glob("*.png")):
                override = LABEL_OVERRIDES.get((subject_id, activity_dir.name, image.stem))
                label = activity_dir / (override or f"{image.stem}.txt")
                if not label.exists():
                    problems.append({
                        "kind": "image_without_label",
                        "path": str(image.relative_to(raw_root)),
                        "detail": "excluded; manual annotation required",
                    })
                    continue
                try:
                    width, height = png_dimensions(image)
                    class_id, box = parse_label(label)
                    index = frame_index(image.stem, subject_id)
                except Exception as error:
                    problems.append({
                        "kind": "invalid_sample",
                        "path": str(image.relative_to(raw_root)),
                        "detail": str(error),
                    })
                    continue

                sample_id = f"s{subject_id:02d}_{activity}_{index:06d}"
                destination_image = output_root / "images" / split / f"{sample_id}.png"
                destination_label = output_root / "labels" / split / f"{sample_id}.txt"
                link_image(image, destination_image)
                label_text = f"{class_id} " + " ".join(f"{value:.6f}" for value in box) + "\n"
                if destination_label.exists():
                    if destination_label.read_text(encoding="utf-8") != label_text:
                        raise FileExistsError(f"conflicting normalized label: {destination_label}")
                else:
                    destination_label.write_text(label_text, encoding="utf-8")

                source_labels_used.add(label.resolve())
                dimensions[(width, height)] += 1
                activity_counts[(split, activity)] += 1
                class_name = "nofall" if class_id == 0 else "fall"
                class_counts[(split, class_name)] += 1
                subject_counts[(split, subject_id)] += 1
                row = {
                    "sample_id": sample_id,
                    "image_path": destination_image.relative_to(output_root).as_posix(),
                    "label_path": destination_label.relative_to(output_root).as_posix(),
                    "subject_id": subject_id,
                    "activity": activity,
                    "video_id": video_id,
                    "frame_index": index,
                    "class_id": class_id,
                    "class_name": class_name,
                    "lighting": lighting,
                    "lux": lux,
                    "width": width,
                    "height": height,
                    "split": split,
                    "source_image": image.relative_to(raw_root).as_posix(),
                    "source_label": label.relative_to(raw_root).as_posix(),
                }
                rows_by_split[split].append(row)
                rename_rows.append({
                    "source_image": row["source_image"],
                    "source_label": row["source_label"],
                    "sample_id": sample_id,
                })

    all_annotation_files = {
        path.resolve() for path in raw_root.rglob("*.txt") if path.name != "classes.txt"
    }
    for unused in sorted(all_annotation_files - source_labels_used):
        problems.append({
            "kind": "label_without_image",
            "path": str(unused.relative_to(raw_root)),
            "detail": "excluded; no matched image after verified overrides",
        })

    all_rows: list[dict[str, object]] = []
    for split in ("train", "validation", "test"):
        rows_by_split[split].sort(key=lambda row: str(row["sample_id"]))
        write_csv(manifests / f"{split}.csv", rows_by_split[split])
        all_rows.extend(rows_by_split[split])
    write_csv(manifests / "all.csv", all_rows)

    with (reports / "invalid_files.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["kind", "path", "detail"])
        writer.writeheader()
        writer.writerows(problems)
    with (reports / "filename_mapping.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_image", "source_label", "sample_id"])
        writer.writeheader()
        writer.writerows(rename_rows)

    stats = {
        "total_valid_samples": len(all_rows),
        "excluded_or_unmatched_files": len(problems),
        "splits": {
            split: {
                "subjects": sorted({int(row["subject_id"]) for row in rows_by_split[split]}),
                "samples": len(rows_by_split[split]),
                "classes": {
                    name: class_counts[(split, name)] for name in ("nofall", "fall")
                },
                "activities": {
                    activity: activity_counts[(split, activity)]
                    for activity in ACTIVITY_NAMES.values()
                },
            }
            for split in ("train", "validation", "test")
        },
        "image_dimensions": {
            f"{width}x{height}": count for (width, height), count in dimensions.items()
        },
        "normalization_contract": {
            "input_size": [320, 320],
            "resize": "preserve aspect ratio",
            "letterbox_rgb": [114, 114, 114],
            "pixel_scale": "float32(pixel) / 255.0",
            "box_format_on_disk": "class_id x_center y_center width height; normalized [0,1]",
            "box_format_for_model": "apply the same resize scale and letterbox offsets as the image",
            "augmentation": "train only",
        },
        "integrity": {
            "split_unit": "subject",
            "subject_overlap": False,
            "raw_data_modified": False,
            "processed_images_are_hard_links": True,
        },
    }
    (reports / "dataset_statistics.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata = {
        "dataset": "CAUCAFall normalized",
        "version": 1,
        "classes": {"0": "nofall", "1": "fall"},
        "raw_root": str(raw_root),
        "split_policy": "subjects 1-7 train, subject 8 validation, subjects 9-10 test",
        "manifest_sha256": hashlib.sha256(
            (manifests / "all.csv").read_bytes()
        ).hexdigest(),
        "notes": "Images remain lossless at 720x480. Apply the normalization contract at load time.",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("Dataset CAUCAFall/Dataset CAUCAFall/CAUCAFall"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("caucafall_normalized"))
    args = parser.parse_args()
    normalize(args.raw_root, args.output_root)


if __name__ == "__main__":
    main()
