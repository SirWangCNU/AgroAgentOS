import { execSync, spawn } from "node:child_process";
import { join } from "node:path";

const root = join(import.meta.dirname, "..");

// Step 1: clean caches
console.log("🚀 Starting fresh dev server...\n");
execSync("node scripts/clean-cache.mjs", { cwd: root, stdio: "inherit" });

// Step 2: start vite dev server
console.log("\n▶ Starting vite dev server...\n");
const child = spawn("npx", ["vite"], {
  cwd: root,
  stdio: "inherit",
  shell: true,
});

child.on("exit", (code) => process.exit(code ?? 0));
