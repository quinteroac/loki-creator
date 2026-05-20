import { inspectProject, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-inspect", (payload) => inspectProject(payload, "hyperframes-inspect"));
