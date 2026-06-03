import { execSync } from "node:child_process";
import { join } from "node:path";

const root = join(import.meta.dirname, "..");

console.log("🚀 Starting fresh build...\n");

// Step 1: clean caches
execSync("node scripts/clean-cache.mjs", { cwd: root, stdio: "inherit" });

// Step 2: run build
console.log("\n▶ Building...\n");
execSync("npx tsc -b && npx vite build", { cwd: root, stdio: "inherit" });

console.log("\n✅ Build complete.");
