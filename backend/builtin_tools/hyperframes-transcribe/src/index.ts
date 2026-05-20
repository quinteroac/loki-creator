import { runTool, transcribe } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-transcribe", (payload) => transcribe(payload, "hyperframes-transcribe"));
