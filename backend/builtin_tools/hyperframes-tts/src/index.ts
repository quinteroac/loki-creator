import { runTool, tts } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-tts", (payload) => tts(payload, "hyperframes-tts"));
