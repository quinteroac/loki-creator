import json
from pathlib import Path

from app.models import ToolDefinition
from app.services.builtin_tools import BUILTIN_TOOLS

BACKEND_DIR = Path(__file__).resolve().parents[2]
BUILTIN_MANIFEST_TOOLS_DIR = BACKEND_DIR / "builtin_tools"
USER_TOOLS_DIR = BACKEND_DIR / "user_tools"


class ToolRegistry:
    def __init__(
        self,
        user_tools_dir: Path = USER_TOOLS_DIR,
        builtin_manifest_tools_dir: Path = BUILTIN_MANIFEST_TOOLS_DIR,
    ) -> None:
        self._user_tools_dir = user_tools_dir
        self._builtin_manifest_tools_dir = builtin_manifest_tools_dir
        self._builtins = BUILTIN_TOOLS

    def list_tools(self) -> list[ToolDefinition]:
        return [*self._builtins, *self._load_builtin_manifest_tools(), *self._load_user_tools()]

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
            tools.append(self._load_manifest_tool(manifest_path, origin="user", exportable=True))

        for manifest_path in sorted(self._user_tools_dir.glob("*/tool.json")):
            tools.append(self._load_manifest_tool(manifest_path, origin="user", exportable=True))

        return tools

    def _load_builtin_manifest_tools(self) -> list[ToolDefinition]:
        if not self._builtin_manifest_tools_dir.exists():
            return []

        return [
            self._load_manifest_tool(manifest_path, origin="built-in", exportable=False)
            for manifest_path in sorted(self._builtin_manifest_tools_dir.glob("*/tool.json"))
        ]

    def _load_manifest_tool(self, manifest_path: Path, *, origin: str, exportable: bool) -> ToolDefinition:
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            data = json.load(manifest_file)

        tool_data = data.get("tool", data)
        tool = ToolDefinition.model_validate(tool_data)
        updates = {"origin": origin, "exportable": exportable}

        if manifest_path.name == "tool.json":
            working_directory = str(manifest_path.parent.relative_to(BACKEND_DIR))
            updates["runtime"] = tool.runtime.model_copy(update={"working_directory": working_directory})

        return tool.model_copy(update=updates)

    def _normalize_tool_id(self, tool_id: str) -> str:
        return tool_id.strip().lower().replace(" ", "-")
