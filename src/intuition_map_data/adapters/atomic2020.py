from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO

NATIVE_SPLITS = frozenset({"train", "dev", "test"})


@dataclass(frozen=True, slots=True)
class Atomic2020Triple:
    head: str
    relation: str
    tail: str
    split: str

    @property
    def is_complete(self) -> bool:
        return bool(self.tail)


def _iter_rows(handle: TextIO, split: str) -> Iterable[Atomic2020Triple]:
    if split not in NATIVE_SPLITS:
        raise ValueError(f"split must be one of {sorted(NATIVE_SPLITS)}")
    reader = csv.reader(handle, delimiter="\t", strict=True)
    for line_number, row in enumerate(reader, start=1):
        if len(row) != 3:
            raise ValueError(
                f"ATOMIC 2020 {split} line {line_number} must have 3 columns"
            )
        values = tuple(value.strip() for value in row)
        if not values[0] or not values[1]:
            raise ValueError(
                f"ATOMIC 2020 {split} line {line_number} has an empty head or relation"
            )
        yield Atomic2020Triple(
            head=values[0],
            relation=values[1],
            tail=values[2],
            split=split,
        )


def iter_atomic2020_tsv(
    path: str | Path, *, split: str
) -> Iterable[Atomic2020Triple]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        yield from _iter_rows(handle, split)


def iter_atomic2020_archive(
    path: str | Path, *, split: str
) -> Iterable[Atomic2020Triple]:
    if split not in NATIVE_SPLITS:
        raise ValueError(f"split must be one of {sorted(NATIVE_SPLITS)}")
    member = f"atomic2020_data-feb2021/{split}.tsv"
    with zipfile.ZipFile(path) as archive:
        try:
            raw = archive.open(member)
        except KeyError as exc:
            raise ValueError(f"ATOMIC 2020 archive is missing {member}") from exc
        with raw, io.TextIOWrapper(raw, encoding="utf-8", newline="") as handle:
            yield from _iter_rows(handle, split)


def validate_atomic2020_archive(path: str | Path) -> dict[str, object]:
    required = {
        "atomic2020_data-feb2021/LICENSE",
        "atomic2020_data-feb2021/README.md",
        *(f"atomic2020_data-feb2021/{split}.tsv" for split in NATIVE_SPLITS),
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = required - names
        if missing:
            raise ValueError(
                f"ATOMIC 2020 archive missing required files: {sorted(missing)}"
            )
        with archive.open("atomic2020_data-feb2021/LICENSE") as handle:
            license_heading = handle.readline().decode("utf-8").strip()
    if license_heading != "Attribution 4.0 International":
        raise ValueError("ATOMIC 2020 archive has unexpected license heading")
    return {
        "required_files_present": True,
        "license_heading": license_heading,
        "native_splits": sorted(NATIVE_SPLITS),
    }
