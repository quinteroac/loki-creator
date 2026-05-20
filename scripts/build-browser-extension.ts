import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const extensionRoot = resolve(repoRoot, "browser-extension");
const distRoot = resolve(extensionRoot, "dist");
const publicDownloadsRoot = resolve(repoRoot, "frontend/public/downloads/browser-extension");
const execFileAsync = promisify(execFile);

async function buildBrowser(target: "chrome" | "firefox") {
  const outDir = resolve(distRoot, target);
  const publicOutDir = resolve(publicDownloadsRoot, target);
  const zipPath = resolve(publicDownloadsRoot, `loki-browser-extension-${target}.zip`);

  await rm(outDir, { force: true, recursive: true });
  await rm(publicOutDir, { force: true, recursive: true });
  await rm(zipPath, { force: true });
  await mkdir(outDir, { recursive: true });
  await cp(resolve(extensionRoot, "src"), resolve(outDir, "src"), { recursive: true });
  await cp(resolve(extensionRoot, "manifests", `${target}.json`), resolve(outDir, "manifest.json"));
  await writeFile(resolve(outDir, "README.txt"), `Load this folder as the Loki Browser Connector ${target} extension.\n`);

  await mkdir(publicDownloadsRoot, { recursive: true });
  await cp(outDir, publicOutDir, { recursive: true });
  await execFileAsync("zip", ["-qr", zipPath, "."], { cwd: outDir });
}

await buildBrowser("chrome");
await buildBrowser("firefox");

console.log(`Built browser extensions in ${distRoot}`);
console.log(`Published browser extension downloads in ${publicDownloadsRoot}`);
