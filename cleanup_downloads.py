"""
Python Automation with ChatGPT (OpenAI API)

This script uses the OpenAI API to:
1. Check the Downloads folder on your computer
2. Find all files older than 60 days
3. Move those files to a "delete" folder

Usage:
    Set the OPENAI_API_KEY environment variable before running:
        PowerShell: $env:OPENAI_API_KEY="your-api-key-here"
        bash/zsh: export OPENAI_API_KEY="your-api-key-here"
    Then run:
        python cleanup_downloads.py
"""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI 

# ── Configuration ────────────────────────────────────────────────────────────
DAYS_THRESHOLD = 60
DOWNLOADS_FOLDER = Path.home() / "Downloads"
DELETE_FOLDER = Path.home() / "delete"
ENV_FILE = Path(__file__).with_name(".env")


def load_api_key() -> str | None:
    """Load OPENAI_API_KEY from the environment or a local .env file."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    if not ENV_FILE.exists():
        return None

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue

        api_key = value.strip().strip('"').strip("'")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            return api_key

    return None


def get_old_files(folder: Path, days: int) -> list[Path]:
    """Return a list of files inside *folder* that are older than *days* days."""
    cutoff = time.time() - days * 86400  # 86400 seconds per day
    old_files = []
    for item in folder.iterdir():
        if item.is_file() and item.stat().st_mtime < cutoff:
            old_files.append(item)
    return old_files


def move_files_to_delete(files: list[Path], delete_folder: Path) -> list[str]:
    """Move each file in *files* to *delete_folder*. Returns list of moved file names."""
    delete_folder.mkdir(parents=True, exist_ok=True)
    moved = []
    for file in files:
        destination = delete_folder / file.name
        # Avoid overwriting an existing file in the delete folder
        if destination.exists():
            stem = file.stem
            suffix = file.suffix
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            destination = delete_folder / f"{stem}_{timestamp}{suffix}"
        shutil.move(str(file), str(destination))
        moved.append(file.name)
    return moved


def build_fallback_advice(old_files: list[Path]) -> str:
    """Return a local cleanup summary when the API is unavailable."""
    if old_files:
        return (
            f"You are cleaning up {len(old_files)} older file(s) from Downloads and moving "
            "them into the delete folder. Tip: review Downloads weekly and archive anything "
            "important before deleting it."
        )

    return (
        "Your Downloads folder does not contain files older than the threshold. Tip: keep "
        "Downloads tidy by sorting or deleting files you no longer need."
    )


def ask_openai(client: OpenAI | None, old_files: list[Path]) -> str:
    """Ask ChatGPT to summarise the cleanup action and provide advice."""
    if client is None:
        return build_fallback_advice(old_files)

    if old_files:
        file_list = "\n".join(f"  - {f.name}" for f in old_files)
        user_message = (
            f"I found the following {len(old_files)} file(s) in my Downloads folder "
            f"that are older than {DAYS_THRESHOLD} days:\n{file_list}\n\n"
            "I am about to move them to a 'delete' folder. "
            "Please briefly summarize what I am doing and give me one short tip about "
            "good file-management hygiene."
        )
    else:
        user_message = (
            f"I scanned my Downloads folder for files older than {DAYS_THRESHOLD} days "
            "and found none. Please confirm this is good news and give one short tip "
            "about keeping a tidy Downloads folder."
        )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that advises on computer file management "
                        "and security best practices. Keep responses concise."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=200,
        )
    except Exception:
        return build_fallback_advice(old_files)

    return response.choices[0].message.content.strip()


def main() -> None:
    # ── Validate environment ──────────────────────────────────────────────────
    api_key = load_api_key()
    if not api_key:
        print(
            "OPENAI_API_KEY is not set. Continuing without API access and using a local "
            "cleanup summary."
        )

    client = OpenAI(api_key=api_key) if api_key else None

    # ── Check Downloads folder ────────────────────────────────────────────────
    if not DOWNLOADS_FOLDER.exists():
        raise FileNotFoundError(
            f"Downloads folder not found: {DOWNLOADS_FOLDER}\n"
            "Please verify the path and try again."
        )

    print(f"Scanning: {DOWNLOADS_FOLDER}")
    print(f"Looking for files older than {DAYS_THRESHOLD} days …\n")

    old_files = get_old_files(DOWNLOADS_FOLDER, DAYS_THRESHOLD)

    if old_files:
        print(f"Found {len(old_files)} file(s) older than {DAYS_THRESHOLD} days:")
        for f in old_files:
            age_days = int((time.time() - f.stat().st_mtime) / 86400)
            print(f"  {f.name}  ({age_days} days old)")
        print()

        # ── Ask OpenAI for context ────────────────────────────────────────────
        print("Asking ChatGPT for advice …")
        advice = ask_openai(client, old_files)
        print(f"\nChatGPT says:\n{advice}\n")

        # ── Move files ────────────────────────────────────────────────────────
        moved = move_files_to_delete(old_files, DELETE_FOLDER)
        print(f"Moved {len(moved)} file(s) to: {DELETE_FOLDER}")
        for name in moved:
            print(f"  ✔ {name}")
    else:
        print(f"No files older than {DAYS_THRESHOLD} days were found.\n")
        print("Asking ChatGPT for a quick tip …")
        advice = ask_openai(client, old_files)
        print(f"\nChatGPT says:\n{advice}\n")

    print("\nDone.")


if __name__ == "__main__":
    main()
