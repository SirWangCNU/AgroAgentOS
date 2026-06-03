import { rmSync, existsSync } from "node:fs";
import { join } from "node:path";
import { execSync } from "node:child_process";

const root = join(import.meta.dirname, "..");

const targets = [
  "node_modules/.vite",
  "node_modules/.cache",
  "dist",
  ".tsbuildinfo",
];

console.log("🧹 Cleaning caches...\n");

for (const t of targets) {
  const full = join(root, t);
  if (existsSync(full)) {
    rmSync(full, { recursive: true, force: true });
    console.log(`  ✔ deleted ${t}`);
  } else {
    console.log(`  – ${t} (not found, skip)`);
  }
}

// Also kill any running vite dev server on port 5173
try {
  if (process.platform === "win32") {
    execSync(
      'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :5173\') do taskkill /f /pid %a',
      { stdio: "ignore", shell: "cmd.exe" }
    );
  } else {
    execSync("lsof -ti:5173 | xargs kill -9 2>/dev/null", {
      stdio: "ignore",
    });
  }
  console.log("  ✔ killed process on port 5173");
} catch {
  console.log("  – no process on port 5173");
}

console.log("\n✅ Done.");
