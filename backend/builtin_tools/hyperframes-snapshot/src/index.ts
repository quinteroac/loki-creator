import { runTool, snapshotProject } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-snapshot", (payload) => snapshotProject(payload, "hyperframes-snapshot"));
