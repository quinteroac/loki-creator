import { renderProject, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-render", (payload) => renderProject(payload, "hyperframes-render"));
