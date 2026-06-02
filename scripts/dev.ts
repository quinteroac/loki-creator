type DevProcess = {
  name: string;
  process: ReturnType<typeof Bun.spawn>;
};

const commands = [
  {
    name: "backend",
    cmd: ["uv", "run", "uvicorn", "app.main:app", "--reload", "--port", "8001"],
    cwd: "backend",
    healthUrl: "http://127.0.0.1:8001/api/health",
  },
  {
    name: "agent-bridge",
    cmd: ["bun", "run", "agent-bridge/server.ts"],
    cwd: ".",
    healthUrl: "http://127.0.0.1:8787/api/health",
  },
  {
    name: "frontend",
    cmd: ["bun", "run", "dev"],
    cwd: "frontend",
  },
] as const;

const processes: DevProcess[] = [];

let shuttingDown = false;

function startProcess({ name, cmd, cwd }: (typeof commands)[number]) {
  const process = Bun.spawn(cmd, {
    cwd,
    stdin: "inherit",
    stdout: "pipe",
    stderr: "pipe",
  });
  processes.push({ name, process });
  console.log(`[dev] started ${name}`);
  void prefixStream(name, process.stdout);
  void prefixStream(name, process.stderr);
  void watchProcessExit(name, process);
}

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

async function waitForHealth(name: string, url: string) {
  let attempt = 0;

  while (!shuttingDown) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        console.log(`[dev] ${name} is ready`);
        return;
      }
    } catch {
      // The service is still starting.
    }

    attempt += 1;
    if (attempt % 10 === 0) {
      console.log(`[dev] waiting for ${name} at ${url}`);
    }
    await Bun.sleep(250);
  }
}

async function watchProcessExit(name: string, process: DevProcess["process"]) {
  const exitCode = await process.exited;
  if (!shuttingDown && exitCode !== 0) {
    console.error(`${name} exited with code ${exitCode}`);
  }
  stopAll(exitCode);
}

process.on("SIGINT", () => stopAll());
process.on("SIGTERM", () => stopAll());

const runtimeCommands = commands.filter((command) => "healthUrl" in command);
const frontendCommand = commands.find((command) => command.name === "frontend");

for (const command of runtimeCommands) {
  startProcess(command);
}

await Promise.all(runtimeCommands.map((command) => waitForHealth(command.name, command.healthUrl)));

if (frontendCommand) {
  startProcess(frontendCommand);
}

await new Promise(() => {});
