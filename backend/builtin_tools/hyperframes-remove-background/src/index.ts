import { removeBackground, runTool } from "../../_hyperframes_shared/index.ts";

await runTool("hyperframes-remove-background", (payload) =>
  removeBackground(payload, "hyperframes-remove-background"),
);
