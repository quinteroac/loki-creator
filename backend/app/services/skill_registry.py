import re
from pathlib import Path
from typing import Any

from app.models import SkillCardAction, SkillDefinition

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
SKILLS_DIR = BACKEND_DIR / "skills"


class SkillRegistry:
    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self._skills_dir = skills_dir

    def list_skills(self) -> list[SkillDefinition]:
        if not self._skills_dir.exists():
            return []

        return [
            self._load_skill(skill_file.parent)
            for skill_file in sorted(self._skills_dir.glob("*/SKILL.md"))
        ]

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        normalized_id = self._normalize_skill_id(skill_id)

        return next(
            (
                skill
                for skill in self.list_skills()
                if skill.id == normalized_id or skill.name.lower() == skill_id.lower()
            ),
            None,
        )

    def _load_skill(self, skill_dir: Path) -> SkillDefinition:
        frontmatter = self._read_frontmatter(skill_dir / "SKILL.md")
        name = str(frontmatter.get("name") or skill_dir.name)
        metadata = frontmatter.get("metadata") if isinstance(frontmatter.get("metadata"), dict) else {}
        loki_metadata = metadata.get("loki") if isinstance(metadata.get("loki"), dict) else {}
        card_action_data = loki_metadata.get("cardAction") if isinstance(loki_metadata.get("cardAction"), dict) else None
        capabilities = loki_metadata.get("capabilities") if isinstance(loki_metadata.get("capabilities"), list) else []

        return SkillDefinition(
            id=self._normalize_skill_id(name),
            name=name,
            description=str(frontmatter.get("description") or ""),
            path=str(skill_dir.relative_to(REPO_ROOT)),
            origin="built-in",
            capabilities=[str(capability) for capability in capabilities],
            card_action=SkillCardAction.model_validate(card_action_data) if card_action_data else None,
        )

    def _read_frontmatter(self, skill_file: Path) -> dict[str, Any]:
        content = skill_file.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", content, flags=re.DOTALL)
        if not match:
            return {}

        return self._parse_simple_yaml(match.group(1))

    def _parse_simple_yaml(self, text: str) -> dict[str, Any]:
        root: dict[str, Any] = {}
        stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

        for raw_line in text.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            key, separator, raw_value = raw_line.strip().partition(":")
            if not separator:
                continue

            while stack and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1]
            value = self._parse_yaml_value(raw_value.strip())
            if value is None:
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
            else:
                parent[key] = value

        return root

    def _parse_yaml_value(self, value: str) -> Any:
        if value == "":
            return None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [item.strip().strip("\"'") for item in inner.split(",")]
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        return value.strip("\"'")

    def _normalize_skill_id(self, skill_id: str) -> str:
        return skill_id.strip().lower().replace(" ", "-")
