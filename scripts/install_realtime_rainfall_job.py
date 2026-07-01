#!/usr/bin/env python3
import os
import plistlib
import subprocess
from pathlib import Path


LABEL = "com.fload.realtime-rainfall"


def main() -> None:
    repo_dir = Path(__file__).resolve().parents[1]
    python_path = repo_dir / ".venv" / "bin" / "python"
    script_path = repo_dir / "scripts" / "run_realtime_rainfall_pipeline.py"
    log_dir = repo_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    if not python_path.exists():
        raise SystemExit("Virtualenv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")

    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            str(python_path),
            str(script_path),
        ],
        "WorkingDirectory": str(repo_dir),
        "StartCalendarInterval": {"Minute": 5},
        "StandardOutPath": str(log_dir / "realtime_rainfall.out.log"),
        "StandardErrorPath": str(log_dir / "realtime_rainfall.err.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", ""),
        },
    }

    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents / f"{LABEL}.plist"

    with plist_path.open("wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], check=True)
    subprocess.run(["launchctl", "enable", f"gui/{os.getuid()}/{LABEL}"], check=True)

    print(f"Installed LaunchAgent: {plist_path}")
    print("Runs every hour at minute 5.")
    print("Pipeline: collect realtime KMA rainfall, then sync the latest rows to Google Sheets when credentials are configured.")
    print(f"Logs: {log_dir}")


if __name__ == "__main__":
    main()
