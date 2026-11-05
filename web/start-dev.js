const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

// Ensure working directory is always `web/` so PostCSS & Tailwind CSS resolve `web/node_modules`
process.chdir(__dirname);
process.env.PATH = `${path.dirname(process.execPath)};${process.env.PATH || ""}`;

function freePort3000() {
  try {
    const out = execSync("netstat -ano -p tcp", { encoding: "utf8" });
    const myPid = process.pid;
    for (const line of out.split(/\r?\n/)) {
      if (line.includes(":3000") && line.includes("LISTENING")) {
        const parts = line.trim().split(/\s+/);
        const pid = parseInt(parts[parts.length - 1], 10);
        if (pid && pid !== myPid) {
          try {
            execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
          } catch (_) {}
        }
      }
    }
  } catch (_) {}
}

freePort3000();

if (process.argv.includes("--clean")) {
  const nextCacheDir = path.join(__dirname, ".next");
  try {
    fs.rmSync(nextCacheDir, { recursive: true, force: true });
  } catch (_) {
    // ignore
  }
  process.argv = process.argv.filter((a) => a !== "--clean");
}

require("./node_modules/next/dist/bin/next");
