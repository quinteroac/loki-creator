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

    def test_comfy_image_upscale_exposes_rtx_arguments(self) -> None:
        skill = SkillRegistry().get_skill("comfy-image-upscale")

        self.assertIsNotNone(skill)
        assert skill is not None
        arguments = {argument.id: argument for argument in skill.arguments}
        self.assertEqual(arguments["engine"].ask_when, "always")
        self.assertEqual([option.value for option in arguments["engine"].options], ["clear-reality", "rtx-vsr"])
        self.assertEqual(arguments["resolution"].depends_on, {"engine": "rtx-vsr"})
        self.assertEqual(arguments["quality"].depends_on, {"engine": "rtx-vsr"})

    def test_comfy_krea2_image_is_dedicated_visible_skill(self) -> None:
        skill = SkillRegistry().get_skill("comfy-krea2-image")

        self.assertIsNotNone(skill)
        assert skill is not None
        self.assertEqual(skill.visibility, "user")
        self.assertEqual(skill.output.kind, "image")
        self.assertIn("krea2", skill.capabilities)
        self.assertIsNotNone(skill.action)
        assert skill.action is not None
        self.assertEqual(skill.action.command, ["python3", "../_comfy_runtime/comfy_action.py"])
        arguments = {argument.id: argument for argument in skill.arguments}
        self.assertEqual([option.value for option in arguments["mode"].options], ["t2i", "r2i"])
        self.assertIn("aspectRatio", arguments)

    def test_comfy_image_generate_no_longer_exposes_krea2_profile(self) -> None:
        skill = SkillRegistry().get_skill("comfy-image-generate")

        self.assertIsNotNone(skill)
        assert skill is not None
        model_profile = next(argument for argument in skill.arguments if argument.id == "modelProfile")
        self.assertNotIn("krea2-turbo", [option.value for option in model_profile.options])


if __name__ == "__main__":
    unittest.main()
