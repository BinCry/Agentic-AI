"""Read existing SKILL.md contracts without introducing a second skill format."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillCatalogError(RuntimeError):
    """Raised for unsafe, missing, or ambiguous skill definitions."""


@dataclass(slots=True, frozen=True)
class SkillDefinition:
    internal_name: str
    declared_name: str
    description: str
    when_to_use: str
    path: Path
    content: str
    content_digest: str
    keywords: tuple[str, ...]


def _parse_frontmatter(content: str) -> dict[str, object]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    result: dict[str, object] = {}
    index = 0
    while index < len(lines):
        raw = lines[index]
        field_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if not field_match:
            index += 1
            continue
        key, value = field_match.group(1), field_match.group(2).strip()
        if value in {">", ">-", "|", "|-"}:
            parts: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index].startswith("  ")):
                if lines[index].strip():
                    parts.append(lines[index].strip())
                index += 1
            result[key] = " ".join(parts)
            continue
        if value.startswith("[") and value.endswith("]"):
            result[key] = tuple(
                item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()
            )
        else:
            result[key] = value.strip("'\"")
        index += 1
    return result


class SkillCatalog:
    def __init__(self, skill_root: Path) -> None:
        self.skill_root = skill_root.resolve()
        self._definitions: dict[str, SkillDefinition] = {}

    def load(self) -> "SkillCatalog":
        if not self.skill_root.is_dir():
            raise SkillCatalogError(f"skill root does not exist: {self.skill_root}")
        definitions: dict[str, SkillDefinition] = {}
        for skill_path in sorted(self.skill_root.rglob("SKILL.md")):
            resolved = skill_path.resolve()
            if skill_path.is_symlink() or not resolved.is_relative_to(self.skill_root):
                continue
            content = resolved.read_text(encoding="utf-8")
            metadata = _parse_frontmatter(content)
            relative_parent = resolved.parent.relative_to(self.skill_root).as_posix()
            internal_name = relative_parent
            declared_name = str(metadata.get("name") or relative_parent)
            definition = SkillDefinition(
                internal_name=internal_name,
                declared_name=declared_name,
                description=str(metadata.get("description") or ""),
                when_to_use=str(metadata.get("when_to_use") or ""),
                path=resolved,
                content=content,
                content_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                keywords=tuple(metadata.get("keywords") or ()),
            )
            definitions[internal_name] = definition
        self._definitions = definitions
        return self

    def all(self) -> tuple[SkillDefinition, ...]:
        return tuple(self._definitions.values())

    def get(self, name: str) -> SkillDefinition | None:
        normalized = name.removeprefix("ck:")
        direct = self._definitions.get(normalized) or self._definitions.get(name)
        if direct:
            return direct
        matches = [
            item
            for item in self._definitions.values()
            if item.declared_name == name or item.declared_name.removeprefix("ck:") == normalized
        ]
        if len(matches) > 1:
            raise SkillCatalogError(f"ambiguous skill name: {name}")
        return matches[0] if matches else None
