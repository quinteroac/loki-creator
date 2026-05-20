import { compositionWrite, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-composition-write", (payload) =>
  compositionWrite(payload, "hyperframes-composition-write"),
);
