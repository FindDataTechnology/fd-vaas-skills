#!/usr/bin/env python3
"""
Unify VAAS material databases into the single `data/vaas.db`.

Sources:
- data/vaas.db  (video domain: videos + distributions + tts/renders/tags/history)
- vaas.db       (root, legacy generic content + distribution)

Destination: data/vaas.db (assets/variants/distribution + preserved video tables).

Idempotent: re-runs skip already-migrated slugs. Backs up both DBs first.
Run:  python mcp-server/scripts/migrate_unify_db.py [--dry-run]
"""

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

VAAS_ROOT = Path(__file__).parent.parent.parent
DATA_DB = VAAS_ROOT / "data" / "vaas.db"
ROOT_DB = VAAS_ROOT / "vaas.db"

TYPE_MAP = {"video": "video", "article": "article", "image": "image",
            "audio": "audio", "presentation": "presentation"}


def backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = db_path.with_suffix(f".db.bak-{stamp}")
    shutil.copy2(db_path, bak)
    return bak


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def slug_exists(conn, slug: str) -> bool:
    return conn.execute("SELECT 1 FROM assets WHERE slug = ?", (slug,)).fetchone() is not None


def migrate_videos(src: sqlite3.Connection, dst: sqlite3.Connection, dry: bool) -> int:
    """videos -> assets (type=video, video_id link)."""
    count = 0
    for row in src.execute("SELECT * FROM videos ORDER BY id"):
        if slug_exists(dst, row["slug"]):
            continue
        if dry:
            print(f"  [dry] would insert asset video: {row['slug']}")
            count += 1
            continue
        dst.execute(
            """INSERT INTO assets (id, slug, type, stage, title, file_path, video_id, metadata, created_at, updated_at)
               VALUES (?, ?, 'video', ?, ?, ?, ?, ?, ?, ?)""",
            (f"video-{row['id']}", row["slug"], row["status"], row["title"],
             f"fd-videos/{row['slug']}/{row['slug']}.mp4", row["id"],
             json.dumps({"description": row["description"]}) if row["description"] else None,
             row["created_at"], row["updated_at"])
        )
        count += 1
    return count


def migrate_distributions_legacy(src: sqlite3.Connection, dst: sqlite3.Connection, dry: bool) -> int:
    """legacy `distributions` (plural, video_id) -> `distribution` (asset_id) + variants."""
    count = 0
    for row in src.execute("SELECT * FROM distributions ORDER BY id DESC"):
        asset = dst.execute(
            "SELECT id FROM assets WHERE video_id = ?", (row["video_id"],)).fetchone()
        if not asset:
            if not dry:
                print(f"  ⚠️  no asset for video_id={row['video_id']}, skipping")
            continue
        if dst.execute("SELECT 1 FROM distribution WHERE video_id = ? AND platform = ?",
                       (row["video_id"], row["platform"])).fetchone():
            continue
        if dry:
            print(f"  [dry] would insert distribution: video {row['video_id']} -> {row['platform']}")
            count += 1
            continue
        dst.execute(
            """INSERT INTO distribution (asset_id, video_id, platform, url, status, published_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (asset["id"], row["video_id"], row["platform"], None,
             row["status"], row["uploaded_at"])
        )
        # Preserve per-platform published title/account/schedule as a variant
        dst.execute(
            """INSERT INTO variants (asset_id, platform, title, extra)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(asset_id, platform) DO NOTHING""",
            (asset["id"], row["platform"], row["title"],
             json.dumps({"account": row["account"], "scheduled_at": row["scheduled_at"]}))
        )
        count += 1
    return count


def migrate_root_content(src: sqlite3.Connection, dst: sqlite3.Connection, dry: bool) -> int:
    """root vaas.db content -> assets."""
    count = 0
    for row in src.execute("SELECT * FROM content ORDER BY created_at"):
        if slug_exists(dst, row["slug"]):
            continue
        mtype = TYPE_MAP.get(row["type"], row["type"])
        if dry:
            print(f"  [dry] would insert asset {mtype}: {row['slug']}")
            count += 1
            continue
        dst.execute(
            """INSERT INTO assets (id, slug, type, stage, title, file_path, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], row["slug"], mtype, row["status"], row["slug"],
             row["file_path"], row["metadata"], row["created_at"], row["updated_at"])
        )
        count += 1
    return count


def migrate_root_distribution(src: sqlite3.Connection, dst: sqlite3.Connection, dry: bool) -> int:
    """root vaas.db distribution -> data/vaas.db distribution (lookup asset by content slug)."""
    count = 0
    for row in src.execute("SELECT * FROM distribution"):
        content = src.execute("SELECT slug FROM content WHERE id = ?", (row["content_id"],)).fetchone()
        if not content:
            continue
        asset = dst.execute("SELECT id FROM assets WHERE slug = ?", (content["slug"],)).fetchone()
        if not asset:
            print(f"  ⚠️  no asset for slug={content['slug']}, skipping distribution")
            continue
        if dst.execute("SELECT 1 FROM distribution WHERE asset_id = ? AND platform = ?",
                       (asset["id"], row["platform"])).fetchone():
            continue
        if dry:
            print(f"  [dry] would insert distribution: {content['slug']} -> {row['platform']}")
            count += 1
            continue
        dst.execute(
            """INSERT INTO distribution (asset_id, platform, url, status, error_message, published_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (asset["id"], row["platform"], row["url"], row["status"],
             row["error_message"], row["published_at"])
        )
        count += 1
    return count


def verify(dst: sqlite3.Connection) -> None:
    assets = dst.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
    videos = dst.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"]
    dist = dst.execute("SELECT COUNT(*) c FROM distribution").fetchone()["c"]
    variants = dst.execute("SELECT COUNT(*) c FROM variants").fetchone()["c"]
    print(f"\n✅ 校验: assets={assets} videos={videos} distribution={dist} variants={variants}")
    # sample: an asset with distribution should resolve lineage
    sample = dst.execute(
        "SELECT a.slug, a.type, a.stage, COUNT(d.id) n FROM assets a "
        "LEFT JOIN distribution d ON d.asset_id = a.id GROUP BY a.id HAVING n > 0 LIMIT 3")
    for r in sample:
        print(f"   {r['slug']} ({r['type']}/{r['stage']}) -> {r['n']} 条 distribution")


def main() -> None:
    dry = "--dry-run" in sys.argv
    if not DATA_DB.exists():
        print("❌ data/vaas.db not found")
        sys.exit(1)
    if not ROOT_DB.exists():
        print("❌ root vaas.db not found")
        sys.exit(1)

    if dry:
        print("══ DRY RUN: 不写入 ══")
    else:
        b1 = backup(DATA_DB)
        b2 = backup(ROOT_DB)
        print(f"备份: {b1.name}, {b2.name}")

    src_data = connect(DATA_DB)
    dst = connect(DATA_DB)
    src_root = connect(ROOT_DB)

    print("→ 迁移 videos → assets")
    n1 = migrate_videos(src_data, dst, dry)
    print(f"  {n1} 条")
    print("→ 迁移旧 distributions → distribution + variants")
    n2 = migrate_distributions_legacy(src_data, dst, dry)
    print(f"  {n2} 条")
    print("→ 迁移根 content → assets")
    n3 = migrate_root_content(src_root, dst, dry)
    print(f"  {n3} 条")
    print("→ 迁移根 distribution → distribution")
    n4 = migrate_root_distribution(src_root, dst, dry)
    print(f"  {n4} 条")

    if not dry:
        dst.commit()
        verify(dst)
    else:
        print("\n[dry] 未提交任何改动")

    src_data.close()
    src_root.close()
    dst.close()


if __name__ == "__main__":
    main()
