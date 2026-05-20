import { registryAdd, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-registry-add", (payload) => registryAdd(payload, "hyperframes-registry-add"));
