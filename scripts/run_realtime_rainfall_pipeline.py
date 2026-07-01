#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    repo_dir = Path(__file__).resolve().parents[1]
    python_path = repo_dir / ".venv" / "bin" / "python"

    if not python_path.exists():
        raise SystemExit("Virtualenv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")

    run(
        [
            str(python_path),
            str(repo_dir / "scripts" / "collect_kma_rainfall.py"),
            "--mode",
            "realtime",
            "--station",
            "159",
        ],
        repo_dir,
    )

    run(
        [
            str(python_path),
            str(repo_dir / "scripts" / "sync_realtime_rainfall_to_sheet.py"),
        ],
        repo_dir,
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
