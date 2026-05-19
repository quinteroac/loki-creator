type DevProcess = {
  name: string;
  process: Bun.Subprocess<"inherit", "inherit", "inherit">;
};

const commands = [
  {
    name: "frontend",
    cmd: ["bun", "run", "dev"],
    cwd: "frontend",
  },
  {
    name: "backend",
    cmd: ["uv", "run", "uvicorn", "app.main:app", "--reload"],
    cwd: "backend",
  },
] as const;

const processes: DevProcess[] = commands.map(({ name, cmd, cwd }) => ({
  name,
  process: Bun.spawn(cmd, {
    cwd,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  }),
}));

let shuttingDown = false;

function stopAll(exitCode = 0) {
  if (shuttingDown) {
    return;
  }

  shuttingDown = true;

  for (const { process } of processes) {
    process.kill();
  }

  process.exit(exitCode);
}

process.on("SIGINT", () => stopAll());
process.on("SIGTERM", () => stopAll());

await Promise.race(
  processes.map(async ({ name, process }) => {
    const exitCode = await process.exited;
    if (!shuttingDown && exitCode !== 0) {
      console.error(`${name} exited with code ${exitCode}`);
    }
    stopAll(exitCode);
  }),
);
