type DevProcess = {
  name: string;
  process: ReturnType<typeof Bun.spawn>;
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
  {
    name: "agent-bridge",
    cmd: ["bun", "run", "agent-bridge/server.ts"],
    cwd: ".",
  },
] as const;

const processes: DevProcess[] = commands.map(({ name, cmd, cwd }) => ({
  name,
  process: Bun.spawn(cmd, {
    cwd,
    stdin: "inherit",
    stdout: "pipe",
    stderr: "pipe",
  }),
}));

let shuttingDown = false;

async function prefixStream(name: string, stream: ReadableStream<Uint8Array> | null) {
  if (!stream) {
    return;
  }

  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let pending = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    pending += decoder.decode(value, { stream: true });
    const lines = pending.split(/\r?\n/);
    pending = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim().length > 0) {
        console.log(`[${name}] ${line}`);
      }
    }
  }

  pending += decoder.decode();
  if (pending.trim().length > 0) {
    console.log(`[${name}] ${pending}`);
  }
}

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

for (const { name, process } of processes) {
  console.log(`[dev] started ${name}`);
  void prefixStream(name, process.stdout);
  void prefixStream(name, process.stderr);
}

await Promise.race(
  processes.map(async ({ name, process }) => {
    const exitCode = await process.exited;
    if (!shuttingDown && exitCode !== 0) {
      console.error(`${name} exited with code ${exitCode}`);
    }
    stopAll(exitCode);
  }),
);
