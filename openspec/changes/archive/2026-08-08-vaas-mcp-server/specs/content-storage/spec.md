# Content Storage Specification

## Overview

SQLite-based content tracking system that stores metadata for all generated content (videos, articles, images, audio, presentations) and their distribution status across platforms.

## ADDED Requirements

### Requirement: Database Schema

The system SHALL maintain a SQLite database at `VAAS/vaas.db` with the following schema.

#### Scenario: Content table structure

**Given** the database is initialized  
**Then** the `content` table exists with columns:
- `id` (TEXT PRIMARY KEY) — UUID
- `type` (TEXT NOT NULL) — `video` / `article` / `image` / `audio` / `presentation`
- `slug` (TEXT NOT NULL) — human-readable identifier
- `file_path` (TEXT NOT NULL) — relative path from `downloads/`
- `metadata` (JSON) — structured metadata
- `status` (TEXT DEFAULT 'draft') — `draft` / `rendered` / `published` / `failed`
- `created_at` (TEXT) — ISO 8601 timestamp
- `updated_at` (TEXT) — ISO 8601 timestamp

#### Scenario: Distribution table structure

**Given** the database is initialized  
**Then** the `distribution` table exists with columns:
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `content_id` (TEXT NOT NULL) — foreign key → content.id
- `platform` (TEXT NOT NULL) — `douyin` / `xiaohongshu` / etc.
- `url` (TEXT) — published URL
- `status` (TEXT DEFAULT 'pending') — `pending` / `publishing` / `success` / `failed`
- `error_message` (TEXT)
- `published_at` (TEXT) — ISO 8601 timestamp

### Requirement: File Organization

The system SHALL organize all generated content under `downloads/` with type-based subdirectories.

#### Scenario: Video file organization

**Given** a video is generated with slug `finddata-brand-2026`  
**Then** all files are stored in `downloads/videos/finddata-brand-2026/`  
**And** the final video is at `downloads/videos/finddata-brand-2026/finddata-brand-2026.mp4`

#### Scenario: Article file organization

**Given** an article is generated with slug `finddata-open-data`  
**Then** all files are stored in `downloads/articles/finddata-open-data/`  
**And** the main content is at `downloads/articles/finddata-open-data/article.md`

### Requirement: List Content Query

The system SHALL provide a `list_content` MCP tool that queries the database.

#### Scenario: List all videos

**Given** the database contains 5 video records  
**When** a user calls `list_content(type="video")`  
**Then** the system returns `{items: [...]}` with 5 items  
**And** each item includes `id`, `type`, `slug`, `status`, `created_at`

#### Scenario: List content with status filter

**Given** the database contains videos with status `rendered` and `published`  
**When** a user calls `list_content(type="video", status="rendered")`  
**Then** the system returns only videos with status `rendered`

### Requirement: Get Content Detail

The system SHALL provide a `get_content` MCP tool that retrieves full content details including distribution history.

#### Scenario: Get content by ID

**Given** a content record exists with ID `550e8400-e29b-41d4-a716-446655440000`  
**When** a user calls `get_content(id="550e8400-e29b-41d4-a716-446655440000")`  
**Then** the system returns the full content record  
**And** includes a `distribution[]` array with all platform publish results

## Implementation Notes

- Database file: `VAAS/vaas.db` (project root)
- All file paths stored relative to `downloads/`
- JSON metadata field replaces task.json for new content
- Existing task.json files remain for backward compatibility
- Migration script provided to import existing task.json into DB
