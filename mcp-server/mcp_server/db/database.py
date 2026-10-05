"""
SQLite database connection and schema initialization.

Single source of truth for VAAS material store: `data/vaas.db`.
Video detail tables (videos/tts_records/renders/tags/history) plus the
generic asset layer (assets/variants/distribution).
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Database file location (VAAS project root / data)
VAAS_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = VAAS_ROOT / "data" / "vaas.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get a SQLite connection with row_factory set for dict-like access.

    Args:
        db_path: Optional custom database path. Defaults to VAAS_ROOT/data/vaas.db

    Returns:
        sqlite3.Connection with row_factory=sqlite3.Row
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path: Optional[Path] = None) -> None:
    """
    Initialize the unified database schema (idempotent, additive only).

    Creates the generic asset layer (assets/variants/distribution) and, on a
    fresh database, the video detail tables. Existing tables are left intact.
    """
    conn = get_connection(db_path)

    # ─── Video detail tables (video domain, preserved) ───────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            script_path TEXT,
            video_width INTEGER DEFAULT 1920,
            video_height INTEGER DEFAULT 1080,
            video_fps INTEGER DEFAULT 30,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            article_markdown_path TEXT,
            article_plain_path TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_slug ON videos(slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tts_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            voice TEXT,
            audio_path TEXT,
            captions_path TEXT,
            captions_raw_path TEXT,
            audio_duration_sec REAL,
            token_count INTEGER,
            fixed_latin_tokens INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS renders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            composition TEXT NOT NULL,
            duration_in_frames INTEGER NOT NULL,
            output_path TEXT NOT NULL,
            props_json TEXT,
            cover_horizontal TEXT,
            cover_vertical TEXT,
            cover_weixin TEXT,
            cover_youtube TEXT,
            poster TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS video_tags (
            video_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (video_id, tag_id),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """)

    # ─── Asset layer (generic material tree) ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,                -- video|article|image|audio|presentation|cover|copy
            stage TEXT NOT NULL DEFAULT 'draft', -- draft|rendered|published|failed
            title TEXT,
            parent_id TEXT REFERENCES assets(id),
            lineage_root TEXT,
            provider TEXT,
            file_path TEXT,
            metadata JSON,
            video_id INTEGER REFERENCES videos(id),
            owner TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_lineage ON assets(lineage_root, stage)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_slug ON assets(slug)")
    _migrate_assets_owner(conn)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            title TEXT,
            body TEXT,
            tags TEXT,
            cover_path TEXT,
            extra JSON,
            UNIQUE(asset_id, platform)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS distribution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            video_id INTEGER REFERENCES videos(id),
            platform TEXT NOT NULL,
            url TEXT,
            status TEXT DEFAULT 'pending',     -- pending|uploaded|failed
            error_message TEXT,
            published_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_distribution_asset ON distribution(asset_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_distribution_platform ON distribution(platform)")
    # One row per (asset, platform): last publish wins
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_distribution_asset_platform ON distribution(asset_id, platform)")

    # ─── Generic asset history (asset_id + video_id, both nullable) ──────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
    """)

    # ─── Hosted mode: async generation jobs (video) ──────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_jobs (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            kind TEXT NOT NULL,                -- video
            status TEXT NOT NULL DEFAULT 'queued', -- queued|running|succeeded|failed|expired
            provider_task_id TEXT,
            slug TEXT,
            asset_id TEXT REFERENCES assets(id),
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_owner ON generation_jobs(owner, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_expires ON generation_jobs(expires_at)")

    # ─── Hosted mode: per-call usage metering ────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            tool TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT,
            units REAL NOT NULL DEFAULT 1,
            unit_type TEXT NOT NULL,           -- image|char|second|render
            credential_source TEXT NOT NULL,   -- pool|default|env
            asset_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_owner ON generation_usage(owner, created_at)")

    conn.commit()
    conn.close()


def _migrate_assets_owner(conn: sqlite3.Connection) -> None:
    """
    Add the `owner` column to a pre-existing assets table (idempotent).

    Fresh databases create the column directly in the DDL above; legacy
    databases get the additive ALTER plus a backfill to the service owner.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
    if not columns:
        return  # table does not exist yet (fresh create runs after this anyway)
    if "owner" not in columns:
        conn.execute("ALTER TABLE assets ADD COLUMN owner TEXT")
    conn.execute("UPDATE assets SET owner = 'service' WHERE owner IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_owner ON assets(owner)")


def ensure_db_exists(db_path: Optional[Path] = None) -> None:
    """
    Ensure the database file exists and schema is initialized.
    """
    path = db_path or DB_PATH
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    init_schema(path)
