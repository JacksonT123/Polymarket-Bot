"""
Polymarket Copy Bot — Interactive Setup
Run: python setup.py
"""
import os
import sys
import subprocess
import shutil
import time
import platform

# ─── Color helpers ───────────────────────────────────────────────────────────

WIN = platform.system() == "Windows"

# Enable ANSI on Windows
if WIN:
    os.system("")

R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[97m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

def c(color, text): return f"{color}{text}{RESET}"
def bold(text): return c(BOLD, text)
def ok(text): print(f"  {c(G, '✓')} {text}")
def err(text): print(f"  {c(R, '✗')} {text}")
def warn(text): print(f"  {c(Y, '!')} {text}")
def info(text): print(f"  {c(C, '→')} {text}")
def hr(ch="─", n=60): print(c(DIM, ch * n))


def banner():
    print()
    print(c(M, BOLD + "  ██████╗  ██████╗ ██╗  ██╗   ██╗    ██████╗  ██████╗ ████████╗" + RESET))
    print(c(M,       "  ██╔══██╗██╔═══██╗██║  ╚██╗ ██╔╝    ██╔══██╗██╔═══██╗╚══██╔══╝"))
    print(c(C,       "  ██████╔╝██║   ██║██║   ╚████╔╝     ██████╔╝██║   ██║   ██║   "))
    print(c(C,       "  ██╔═══╝ ██║   ██║██║    ╚██╔╝      ██╔══██╗██║   ██║   ██║   "))
    print(c(B,       "  ██║     ╚██████╔╝███████╗██║        ██████╔╝╚██████╔╝   ██║   "))
    print(c(B,       "  ╚═╝      ╚═════╝ ╚══════╝╚═╝        ╚═════╝  ╚═════╝   ╚═╝   "))
    print()
    print(c(DIM, "  " + "─" * 58))
    print(f"  {c(W, 'Polymarket Copy Bot v2.3')}  {c(DIM, '— automated copy trading')}")
    print(c(DIM, "  " + "─" * 58))
    print()


def menu(title, options):
    """Show a numbered menu, return chosen index (0-based)."""
    hr()
    print(f"\n  {bold(title)}\n")
    for i, (label, desc) in enumerate(options, 1):
        print(f"  {c(C, str(i) + '.')} {c(W, label):<30}  {c(DIM, desc)}")
    print(f"  {c(Y, '0.')} {c(DIM, 'Exit')}")
    print()
    while True:
        try:
            raw = input(f"  {c(M, '▶')} Choose: ").strip()
            n = int(raw)
            if n == 0:
                goodbye()
            if 1 <= n <= len(options):
                return n - 1
        except (ValueError, KeyboardInterrupt):
            pass
        warn("Enter a number from the list.")


def goodbye():
    print(f"\n  {c(G, 'Goodbye!')} Run {c(C, 'python setup.py')} any time.\n")
    sys.exit(0)


def pause():
    input(f"\n  {c(DIM, 'Press Enter to return to menu...')}")


# ─── Actions ─────────────────────────────────────────────────────────────────

def check_prereqs():
    print(f"\n  {bold('Checking prerequisites...')}\n")
    checks = [
        ("Python 3.12+", lambda: sys.version_info >= (3, 12), f"Python {sys.version.split()[0]}"),
        ("uv",           lambda: shutil.which("uv") is not None, "package manager"),
        ("git",          lambda: shutil.which("git") is not None, "version control"),
        ("PostgreSQL",   lambda: shutil.which("psql") is not None, "database"),
    ]
    all_ok = True
    for name, check_fn, note in checks:
        try:
            passed = check_fn()
        except Exception:
            passed = False
        if passed:
            ok(f"{name:<20}  {c(DIM, note)}")
        else:
            err(f"{name:<20}  {c(R, 'NOT FOUND')}")
            all_ok = False
    if not all_ok:
        print()
        warn("Some prerequisites are missing. Install them and re-run.")
    else:
        print()
        ok(c(G, "All prerequisites satisfied!"))
    pause()


def install_deps():
    print(f"\n  {bold('Installing Python dependencies...')}\n")
    info("Running: uv sync --system-certs")
    print()
    result = subprocess.run(["uv", "sync", "--system-certs"], cwd=os.path.dirname(__file__))
    print()
    if result.returncode == 0:
        ok("Dependencies installed.")
    else:
        err("uv sync failed. Check error output above.")
    pause()


def setup_env():
    print(f"\n  {bold('Environment (.env) setup')}\n")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    example_path = os.path.join(os.path.dirname(__file__), ".env.example")

    if os.path.exists(env_path):
        warn(".env already exists. Editing existing file.")
    else:
        if os.path.exists(example_path):
            shutil.copy(example_path, env_path)
            ok("Created .env from .env.example")
        else:
            open(env_path, "w").close()
            ok("Created blank .env")

    print()
    print(f"  {c(W, 'Required settings:')}\n")

    fields = [
        ("DATABASE_URL",            "PostgreSQL URL",         f"postgresql+asyncpg://postgres:postgres@localhost:5432/polymarket_bot"),
        ("TRADING_MODE",            "PAPER or LIVE",          "PAPER"),
        ("POLYMARKET_PRIVATE_KEY",  "Live mode only (blank)", ""),
        ("DISCORD_WEBHOOK_URL",     "Notifications (optional)",""),
    ]

    current = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    current[k.strip()] = v.strip()

    new_vals = {}
    for key, label, default in fields:
        existing = current.get(key, default)
        masked = "***" if "KEY" in key or "SECRET" in key or "PASS" in key else existing
        print(f"  {c(C, key)}")
        print(f"  {c(DIM, label)}  {c(DIM, '[' + masked + ']')}")
        raw = input(f"  {c(M, '▶')} New value (Enter to keep): ").strip()
        new_vals[key] = raw if raw else existing
        print()

    # Write back
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    updated_keys = set()
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=")[0].strip()
            if k in new_vals:
                result_lines.append(f"{k}={new_vals[k]}\n")
                updated_keys.add(k)
                continue
        result_lines.append(line)

    for k, v in new_vals.items():
        if k not in updated_keys:
            result_lines.append(f"{k}={v}\n")

    with open(env_path, "w") as f:
        f.writelines(result_lines)

    ok(".env saved.")
    pause()


def run_migrations():
    print(f"\n  {bold('Running database migrations...')}\n")

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    db_url = ""
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip()

    if not db_url:
        err("DATABASE_URL not set in .env. Run 'Setup .env' first.")
        pause()
        return

    info(f"Database: {c(DIM, db_url[:60] + ('...' if len(db_url) > 60 else ''))}")
    info("Running: uv run alembic upgrade head")
    print()

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(__file__),
        env=env,
    )
    print()
    if result.returncode == 0:
        ok("Migrations applied.")
    else:
        err("Migration failed. Check output above.")
    pause()


def seed_db():
    print(f"\n  {bold('Seeding initial equity snapshot...')}\n")
    info("Running: uv run python scripts/seed_db.py")
    print()

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env = os.environ.copy()
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()

    result = subprocess.run(
        ["uv", "run", "python", "scripts/seed_db.py"],
        cwd=os.path.dirname(__file__),
        env=env,
    )
    print()
    if result.returncode == 0:
        ok("Database seeded with $1,000 starting equity.")
    else:
        err("Seed failed. Check output above.")
    pause()


def start_bot():
    print(f"\n  {bold('Starting the bot...')}\n")
    info("Command: uv run polymarket-bot start")
    info("Dashboard will open at http://localhost:8000")
    warn("This runs in the foreground. Press Ctrl+C to stop.")
    print()
    confirm = input(f"  {c(M, '▶')} Start now? [y/N]: ").strip().lower()
    if confirm != "y":
        info("Cancelled.")
        pause()
        return
    print()
    subprocess.run(["uv", "run", "polymarket-bot", "start"], cwd=os.path.dirname(__file__))
    pause()


def bot_status():
    print(f"\n  {bold('Bot status')}\n")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env = os.environ.copy()
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    subprocess.run(["uv", "run", "polymarket-bot", "status"], cwd=os.path.dirname(__file__), env=env)
    pause()


def run_tests():
    print(f"\n  {bold('Running test suite...')}\n")
    info("Running: uv run pytest tests/ -v")
    print()
    subprocess.run(["uv", "run", "pytest", "tests/", "-v"], cwd=os.path.dirname(__file__))
    pause()


def show_config():
    print(f"\n  {bold('Current configuration')}\n")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        warn(".env not found. Run 'Setup .env' first.")
        pause()
        return
    with open(env_path) as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                if line.startswith("#"):
                    print(f"  {c(DIM, line)}")
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v_display = v.strip()
                if any(x in k for x in ("KEY", "SECRET", "PASS", "TOKEN")):
                    v_display = "***" if v_display else c(DIM, "(not set)")
                elif not v_display:
                    v_display = c(DIM, "(not set)")
                print(f"  {c(C, k):<40}  {c(W, v_display)}")
    pause()


def full_setup():
    print(f"\n  {bold('Full first-time setup')}\n")
    print(f"  {c(DIM, 'This will run: prereqs → deps → .env → migrations → seed')}\n")
    confirm = input(f"  {c(M, '▶')} Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        info("Cancelled.")
        pause()
        return

    steps = [
        ("Checking prerequisites", check_prereqs),
        ("Installing dependencies", install_deps),
        ("Configuring .env",        setup_env),
        ("Running migrations",      run_migrations),
        ("Seeding database",        seed_db),
    ]

    for label, fn in steps:
        hr("·")
        print(f"\n  {c(Y, '▶')} {bold(label)}")
        fn()


# ─── Main loop ───────────────────────────────────────────────────────────────

MAIN_MENU = [
    ("Full first-time setup",  "install deps, configure .env, migrate DB, seed"),
    ("Check prerequisites",    "verify Python, uv, git, PostgreSQL"),
    ("Install dependencies",   "uv sync --system-certs"),
    ("Setup .env",             "configure database URL, trading mode, keys"),
    ("Run DB migrations",      "alembic upgrade head"),
    ("Seed database",          "add $1,000 starting equity snapshot"),
    ("Start the bot",          "launch bot + dashboard (foreground)"),
    ("Bot status",             "quick status: wallets, positions, equity"),
    ("Run tests",              "pytest tests/"),
    ("Show config",            "print current .env values"),
]

ACTIONS = [
    full_setup,
    check_prereqs,
    install_deps,
    setup_env,
    run_migrations,
    seed_db,
    start_bot,
    bot_status,
    run_tests,
    show_config,
]


def main():
    banner()
    while True:
        choice = menu("What do you want to do?", MAIN_MENU)
        print()
        ACTIONS[choice]()


if __name__ == "__main__":
    main()
