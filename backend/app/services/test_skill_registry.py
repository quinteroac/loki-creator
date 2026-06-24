from __future__ import annotations

import unittest

from app.services.skill_registry import SkillRegistry


class SkillRegistryTest(unittest.TestCase):
    def test_hyperframes_text_video_skill_is_visible(self) -> None:
        skill = SkillRegistry().get_skill("hyperframes-text-video")

        self.assertIsNotNone(skill)
        assert skill is not None
        self.assertEqual(skill.visibility, "user")
        self.assertEqual(skill.output.kind, "video")
        self.assertIn("hyperframes", skill.capabilities)
        self.assertIsNotNone(skill.action)
        assert skill.action is not None
        self.assertEqual(skill.action.command, ["python3", "scripts/hyperframes_text_video_action.py"])
        argument_ids = [argument.id for argument in skill.arguments]
        self.assertIn("videoResolution", argument_ids)
        self.assertIn("aspectRatio", argument_ids)

    def test_comfy_imagedescribe_skill_is_internal(self) -> None:
        skill = SkillRegistry().get_skill("comfy-imagedescribe")

        self.assertIsNotNone(skill)
        assert skill is not None
        self.assertEqual(skill.visibility, "internal")
        self.assertEqual(skill.output.kind, "text")
        self.assertIn("image-description", skill.capabilities)
        self.assertIsNotNone(skill.action)
        assert skill.action is not None
        self.assertEqual(skill.action.command, ["python3", "../_comfy_runtime/comfy_action.py"])


if __name__ == "__main__":
    unittest.main()
