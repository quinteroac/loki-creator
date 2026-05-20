import { lintProject, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-lint", (payload) => lintProject(payload, "hyperframes-lint"));
