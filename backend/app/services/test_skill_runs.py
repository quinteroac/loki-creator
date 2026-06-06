from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.models import SkillDefinition, SkillPackagedRunRequest
from app.services.skill_runs import SkillRunService


class StaticSkillRegistry:
    def __init__(self, skill: SkillDefinition) -> None:
        self.skill = skill

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        return self.skill if skill_id == self.skill.id else None


class PackagedSkillRunTest(unittest.TestCase):
    def create_service(self, root: Path) -> SkillRunService:
        skill = SkillDefinition(
            id="imagegen",
            name="Imagegen",
            description="Generate images.",
            path=str(root / "skills" / "imagegen"),
            capabilities=["image-generation"],
        )
        return SkillRunService(registry=StaticSkillRegistry(skill))  # type: ignore[arg-type]

    def test_create_packaged_run_copies_saved_path_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.services.card_packager.ARTIFACTS_ROOT",
            Path(tmpdir) / ".loki",
        ):
            root = Path(tmpdir)
            source = root / "external" / "generated.png"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (32, 16), "blue").save(source)

            service = self.create_service(root)
            run = service.create_packaged_run(
                SkillPackagedRunRequest(
                    skillId="imagegen",
                    prompt="blue test image",
                    rawResult={
                        "artifacts": [
                            {
                                "path": str(source),
                                "kind": "image",
                                "mimeType": "image/png",
                                "title": "Blue image",
                                "metadata": {"sourceTool": "codex_generate_image"},
                            }
                        ]
                    },
                )
            )

            self.assertEqual(run.status, "succeeded")
            self.assertEqual(len(run.result.cards), 1)  # type: ignore[union-attr]
            card = run.result.cards[0]  # type: ignore[union-attr]
            self.assertEqual(card.name, "Blue image")
            self.assertEqual(card.metadata.kind, "image")
            self.assertEqual(card.metadata.width, 32)
            self.assertEqual(card.metadata.height, 16)
            artifact_url = card.metadata.artifact_url
            self.assertTrue(artifact_url.startswith("/api/artifacts/skills/imagegen/"))
            self.assertTrue((root / ".loki" / artifact_url.removeprefix("/api/artifacts/")).is_file())

    def test_create_packaged_run_materializes_inline_image_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.services.card_packager.ARTIFACTS_ROOT",
            Path(tmpdir) / ".loki",
        ):
            root = Path(tmpdir)
            source = root / "inline.png"
            Image.new("RGB", (18, 12), "red").save(source)
            data_url = "data:image/png;base64," + base64.b64encode(source.read_bytes()).decode("ascii")

            service = self.create_service(root)
            run = service.create_packaged_run(
                SkillPackagedRunRequest(
                    skillId="imagegen",
                    prompt="red test image",
                    rawResult={
                        "artifacts": [
                            {
                                "dataUrl": data_url,
                                "kind": "image",
                                "mimeType": "image/png",
                                "title": "Inline image",
                            }
                        ]
                    },
                )
            )

            self.assertEqual(run.status, "succeeded")
            self.assertEqual(len(run.result.cards), 1)  # type: ignore[union-attr]
            card = run.result.cards[0]  # type: ignore[union-attr]
            self.assertEqual(card.name, "Inline image")
            self.assertEqual(card.metadata.kind, "image")
            self.assertEqual(card.metadata.width, 18)
            self.assertEqual(card.metadata.height, 12)
            self.assertTrue((root / ".loki" / card.metadata.artifact_url.removeprefix("/api/artifacts/")).is_file())


if __name__ == "__main__":
    unittest.main()
