import { runTool, runtimeCheck } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-runtime-check", (payload) => runtimeCheck(payload, "hyperframes-runtime-check"));
