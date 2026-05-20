import { projectCreate, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-project-create", (payload) => projectCreate(payload, "hyperframes-project-create"));
