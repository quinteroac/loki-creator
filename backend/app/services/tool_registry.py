import json
from pathlib import Path

from app.models import ToolDefinition
from app.services.builtin_tools import BUILTIN_TOOLS

USER_TOOLS_DIR = Path(__file__).resolve().parents[2] / "user_tools"


class ToolRegistry:
    def __init__(self, user_tools_dir: Path = USER_TOOLS_DIR) -> None:
        self._user_tools_dir = user_tools_dir
        self._builtins = BUILTIN_TOOLS

    def list_tools(self) -> list[ToolDefinition]:
        return [*self._builtins, *self._load_user_tools()]

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        normalized_id = self._normalize_tool_id(tool_id)
        return next(
            (
                tool
                for tool in self.list_tools()
                if tool.id == normalized_id or tool.slug == normalized_id or tool.name.lower() == tool_id.lower()
            ),
            None,
        )

    def _load_user_tools(self) -> list[ToolDefinition]:
        if not self._user_tools_dir.exists():
            return []

        tools: list[ToolDefinition] = []
        for manifest_path in sorted(self._user_tools_dir.glob("*.json")):
            with manifest_path.open("r", encoding="utf-8") as manifest_file:
                data = json.load(manifest_file)

            tool_data = data.get("tool", data)
            tool = ToolDefinition.model_validate(tool_data)
            tools.append(tool.model_copy(update={"origin": "user", "exportable": True}))

        return tools

    def _normalize_tool_id(self, tool_id: str) -> str:
        return tool_id.strip().lower().replace(" ", "-")
