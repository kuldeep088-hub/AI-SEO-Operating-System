#!/usr/bin/env node
// `npm run dev` used to start Next.js alone. That leaves the API on :8000 dead, so
// "Continue with Google" — an <a href> straight to ${API_URL}/v1/auth/google/start —
// navigates the browser to ERR_CONNECTION_REFUSED with nothing in any log to explain it.
//
// Starting the web app without the API is almost never what you want, so `dev` now
// delegates to run.sh (Postgres, Ollama, API, worker, web). run.sh exports SEOOS_STACK=1
// before it calls back in here, and that is what stops the recursion.
//
// Genuinely want the web server on its own? `npm run dev:web`.

import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(webDir, "..", "..");

const inStack = process.env.SEOOS_STACK === "1";

const [command, args, cwd] = inStack
  ? [resolve(webDir, "node_modules/.bin/next"), ["dev", "-p", "3000"], webDir]
  : [resolve(repoRoot, "run.sh"), [], repoRoot];

if (!inStack) {
  console.log("▸ starting the full stack via run.sh — the API on :8000 is what");
  console.log("  Google sign-in talks to, and web alone cannot serve it.");
  console.log("  Web server only: npm run dev:web\n");
}

const child = spawn(command, args, { cwd, stdio: "inherit" });

child.on("error", (err) => {
  console.error(`Failed to start ${command}: ${err.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
