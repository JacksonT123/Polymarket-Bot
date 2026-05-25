"""
start.py — launch bot + dashboard in one terminal.
Usage: uv run python start.py
Ctrl+C to stop both.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).parent
DASHBOARD = ROOT / "dashboard"

BOT_CMD = [sys.executable, "-m", "bot.main"]
DASH_CMD = ["pnpm", "dev"]

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"


def _stream(proc: subprocess.Popen, prefix: str, color: str) -> None:
    tag = f"{BOLD}{color}[{prefix}]{RESET} "
    for line in proc.stdout:  # type: ignore[union-attr]
        sys.stdout.write(tag + line)
        sys.stdout.flush()


def main() -> None:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    print(f"{BOLD}Starting Polymarket bot + dashboard…{RESET}\n")

    bot = subprocess.Popen(
        BOT_CMD,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    dash = subprocess.Popen(
        DASH_CMD,
        cwd=DASHBOARD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(sys.platform == "win32"),
    )

    threading.Thread(target=_stream, args=(bot, "BOT", CYAN), daemon=True).start()
    threading.Thread(target=_stream, args=(dash, "DASH", YELLOW), daemon=True).start()

    print(f"  {CYAN}[BOT]{RESET}  pid={bot.pid}")
    print(f"  {YELLOW}[DASH]{RESET} pid={dash.pid}  → http://localhost:3000\n")
    print("Press Ctrl+C to stop both.\n")

    try:
        # Exit as soon as either process dies
        while True:
            if bot.poll() is not None:
                print(f"\n{BOLD}{CYAN}[BOT]{RESET} exited (code {bot.returncode})")
                break
            if dash.poll() is not None:
                print(f"\n{BOLD}{YELLOW}[DASH]{RESET} exited (code {dash.returncode})")
                break
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopping…{RESET}")
    finally:
        for proc in (bot, dash):
            if proc.poll() is None:
                proc.terminate()
        for proc in (bot, dash):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Stopped.")


if __name__ == "__main__":
    main()
