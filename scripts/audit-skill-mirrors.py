#!/usr/bin/env python3
"""
Audit mirrored SKILL.md files across ClaudeKit skill roots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_ROOTS = (
    (".claude", ".claude/skills"),
    (".codex", ".codex/skills"),
    (".agents", ".agents/skills"),
    (".cursor", ".cursor/skills"),
)

DRIFT_STATUSES = {"full-drifted", "partial-drifted"}
LISTED_STATUSES = ("full-drifted", "partial-drifted", "single-root-only")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit mirrored SKILL.md files across ClaudeKit skill roots."
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root used for resolving relative root paths.",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help=(
            "Skill root to audit. Repeat for multiple roots. "
            "If omitted, defaults to .claude/.codex/.agents/.cursor skill roots."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the audit report as JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum items to print per status section in text mode.",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit with code 1 when any skill content drift is detected.",
    )
    return parser.parse_args()


def parse_root_spec(spec: str, repo_root: Path) -> tuple[str, Path]:
    if "=" in spec:
        label, raw_path = spec.split("=", 1)
    else:
        raw_path = spec
        candidate = Path(raw_path)
        label = candidate.parent.name if candidate.name == "skills" else candidate.name

    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path
    return label, path.resolve()


def resolve_roots(repo_root: Path, root_specs: list[str]) -> list[tuple[str, Path]]:
    if root_specs:
        return [parse_root_spec(spec, repo_root) for spec in root_specs]
    return [(label, (repo_root / relative_path).resolve()) for label, relative_path in DEFAULT_ROOTS]


def normalized_sha256(path: Path) -> str:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def scan_root(root_label: str, root_path: Path) -> dict[str, dict[str, str]]:
    skills: dict[str, dict[str, str]] = {}
    if not root_path.exists():
        return skills

    for skill_file in sorted(root_path.rglob("SKILL.md")):
        if skill_file.is_symlink():
            continue
        relative_file = skill_file.relative_to(root_path)
        skill_id = relative_file.parent.as_posix()
        skills[skill_id] = {
            "root": root_label,
            "hash": normalized_sha256(skill_file),
            "path": relative_file.as_posix(),
        }
    return skills


def classify_skill(root_labels: list[str], entries: dict[str, dict[str, str]]) -> str:
    hashes = {entry["hash"] for entry in entries.values()}
    if len(entries) == len(root_labels):
        return "fully-mirrored" if len(hashes) == 1 else "full-drifted"
    if len(hashes) == 1:
        return "single-root-only" if len(entries) == 1 else "partial-consistent"
    return "partial-drifted"


def build_report(roots: list[tuple[str, Path]]) -> dict[str, object]:
    root_entries = []
    per_root: dict[str, dict[str, dict[str, str]]] = {}

    for label, path in roots:
        root_entries.append({"label": label, "path": str(path), "exists": path.exists()})
        per_root[label] = scan_root(label, path)

    root_labels = [entry["label"] for entry in root_entries]
    all_skill_ids = sorted(
        {
            skill_id
            for scanned_root in per_root.values()
            for skill_id in scanned_root.keys()
        }
    )

    summary = Counter()
    skills = []
    for skill_id in all_skill_ids:
        entries = {
            root_label: per_root[root_label][skill_id]
            for root_label in root_labels
            if skill_id in per_root[root_label]
        }
        status = classify_skill(root_labels, entries)
        summary[status] += 1
        skills.append(
            {
                "skill": skill_id,
                "status": status,
                "present_in": list(entries.keys()),
                "roots": entries,
            }
        )

    return {
        "roots": root_entries,
        "summary": {
            "root_count": len(root_labels),
            "unique_skills": len(all_skill_ids),
            "fully_mirrored": summary["fully-mirrored"],
            "full_drifted": summary["full-drifted"],
            "partial_consistent": summary["partial-consistent"],
            "partial_drifted": summary["partial-drifted"],
            "single_root_only": summary["single-root-only"],
            "drifted_total": summary["full-drifted"] + summary["partial-drifted"],
        },
        "skills": skills,
    }


def format_root_hashes(skill: dict[str, object]) -> str:
    roots: dict[str, dict[str, str]] = skill["roots"]  # type: ignore[assignment]
    return ", ".join(
        f"{root_label}={root_entry['hash'][:8]}"
        for root_label, root_entry in sorted(roots.items())
    )


def print_text_report(report: dict[str, object], limit: int) -> None:
    summary: dict[str, int] = report["summary"]  # type: ignore[assignment]
    skills: list[dict[str, object]] = report["skills"]  # type: ignore[assignment]
    roots: list[dict[str, object]] = report["roots"]  # type: ignore[assignment]

    print("Skill mirror audit")
    print(f"Roots: {', '.join(root['label'] for root in roots)}")
    print("Summary:")
    print(f"- unique skills: {summary['unique_skills']}")
    print(f"- fully mirrored: {summary['fully_mirrored']}")
    print(f"- full drifted: {summary['full_drifted']}")
    print(f"- partial drifted: {summary['partial_drifted']}")
    print(f"- partial consistent: {summary['partial_consistent']}")
    print(f"- single root only: {summary['single_root_only']}")

    for status in LISTED_STATUSES:
        matching = [skill for skill in skills if skill["status"] == status]
        if not matching:
            continue
        print(f"\n{status}:")
        shown = matching if limit <= 0 else matching[:limit]
        for skill in shown:
            print(f"- {skill['skill']}: {format_root_hashes(skill)}")
        if limit > 0 and len(matching) > limit:
            print(f"- ... {len(matching) - limit} more")


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    roots = resolve_roots(repo_root, args.root)
    report = build_report(roots)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_text_report(report, args.limit)

    summary: dict[str, int] = report["summary"]  # type: ignore[assignment]
    if args.fail_on_drift and summary["drifted_total"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
