const fs = require("fs");
const path = require("path");

// Ensure working directory is always `web/` so PostCSS & Tailwind CSS resolve `web/node_modules`
process.chdir(__dirname);
process.env.PATH = `${path.dirname(process.execPath)};${process.env.PATH || ""}`;

// Clear stale .next cache if CSS was previously compiled from wrong working directory
const nextCacheDir = path.join(__dirname, ".next");
try {
  fs.rmSync(nextCacheDir, { recursive: true, force: true });
} catch (_) {
  // ignore
}

require("./node_modules/next/dist/bin/next");

