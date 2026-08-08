#!/usr/bin/env python3
"""
Migration script to import existing task.json files into the VAAS database.

Scans downloads/fd-videos/*/task.json and inserts records into the content table.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.db import init_schema, insert_content, get_content_by_slug
from mcp_server.utils import VAAS_ROOT


def migrate_video_task(task_json_path: Path) -> bool:
    """
    Migrate a single video task.json to the database.

    Args:
        task_json_path: Path to task.json file

    Returns:
        True if migrated successfully, False if already exists or error
    """
    try:
        task_data = json.loads(task_json_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ERROR: Failed to read {task_json_path}: {e}")
        return False

    slug = task_data.get("slug")
    if not slug:
        print(f"  ERROR: No slug found in {task_json_path}")
        return False

    # Check if already exists
    existing = get_content_by_slug(slug)
    if existing:
        print(f"  SKIP: {slug} already exists in database")
        return False

    # Determine file path
    task_dir = task_json_path.parent
    video_file = task_dir / f"{slug}.mp4"
    if video_file.exists():
        file_path = f"fd-videos/{slug}/{slug}.mp4"
    else:
        # Fallback to first mp4 in directory
        mp4_files = list(task_dir.glob("*.mp4"))
        if mp4_files:
            file_path = f"fd-videos/{slug}/{mp4_files[0].name}"
        else:
            file_path = f"fd-videos/{slug}/"

    # Determine status
    status = task_data.get("status", "draft")

    # Build metadata
    metadata = {
        "script": task_data.get("script"),
        "video": task_data.get("video"),
        "tts": task_data.get("tts"),
        "render": task_data.get("render"),
        "distribution": task_data.get("distribution", []),
        "migrated_from": "task.json",
    }

    # Insert into database
    try:
        content_id = insert_content(
            type="video",
            slug=slug,
            file_path=file_path,
            metadata=metadata,
            status=status
        )
        print(f"  OK: Migrated {slug} (id={content_id})")
        return True
    except Exception as e:
        print(f"  ERROR: Failed to insert {slug}: {e}")
        return False


def main():
    """Main migration function."""
    print("VAAS Task JSON to Database Migration")
    print("=" * 50)

    # Initialize database
    init_schema()
    print("Database initialized")

    # Scan for task.json files
    downloads_dir = VAAS_ROOT / "downloads"

    # Migrate fd-videos (legacy)
    fd_videos_dir = downloads_dir / "fd-videos"
    if fd_videos_dir.exists():
        print(f"\nScanning {fd_videos_dir}...")
        task_json_files = list(fd_videos_dir.glob("*/task.json"))
        print(f"Found {len(task_json_files)} task.json files")

        migrated = 0
        skipped = 0
        errors = 0

        for task_json_path in task_json_files:
            result = migrate_video_task(task_json_path)
            if result:
                migrated += 1
            elif result is False:
                # Check if it was skipped or error
                existing = get_content_by_slug(task_json_path.parent.name)
                if existing:
                    skipped += 1
                else:
                    errors += 1

        print(f"\nMigration summary:")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")

    # Migrate videos (new structure)
    videos_dir = downloads_dir / "videos"
    if videos_dir.exists():
        print(f"\nScanning {videos_dir}...")
        task_json_files = list(videos_dir.glob("*/task.json"))
        print(f"Found {len(task_json_files)} task.json files")

        migrated = 0
        skipped = 0
        errors = 0

        for task_json_path in task_json_files:
            result = migrate_video_task(task_json_path)
            if result:
                migrated += 1
            elif result is False:
                existing = get_content_by_slug(task_json_path.parent.name)
                if existing:
                    skipped += 1
                else:
                    errors += 1

        print(f"\nMigration summary:")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
