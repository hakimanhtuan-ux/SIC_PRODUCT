import os
from pathlib import Path
import re
import subprocess
import sys
import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))


def free_port_8000() -> None:
    """Frees port 8000 if a previous stale uvicorn process is still holding it."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"], text=True, stderr=subprocess.DEVNULL
        )
        my_pid = os.getpid()
        for line in out.splitlines():
            if ":8000" in line and "LISTENING" in line:
                parts = re.split(r"\s+", line.strip())
                pid = int(parts[-1])
                if pid != my_pid and pid > 0:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
    except Exception:
        pass


if __name__ == "__main__":
    free_port_8000()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)

