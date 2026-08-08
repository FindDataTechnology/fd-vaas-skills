# Publishing Specification

## Overview

MCP tools for automated multi-platform publishing of videos and articles. Wraps existing `fd-vaas-publish-videos` and `fd-vaas-publish-docs` skills, with DB tracking of distribution status.

## ADDED Requirements

### Requirement: Video Publishing

The system SHALL provide a `publish_video` MCP tool that publishes videos to multiple platforms.

#### Scenario: Publish video to default platforms

**Given** a video exists with slug `finddata-brand-2026` and status `rendered`  
**When** a user calls `publish_video(slug="finddata-brand-2026", title="寻数科技")`  
**Then** the system publishes to platforms specified in `.env PLATFORMS`  
**And** returns `{results: [{platform, status, url, published_at}]}`  
**And** updates the `distribution` table with results  
**And** updates `content.status` to `published` if all platforms succeeded

#### Scenario: Publish video to specific platforms

**Given** a video exists with slug `finddata-brand-2026`  
**When** a user calls `publish_video(slug="finddata-brand-2026", platforms=["douyin", "xiaohongshu"])`  
**Then** the system publishes only to douyin and xiaohongshu

#### Scenario: Partial publish failure

**Given** a video is being published to 3 platforms  
**When** one platform fails (e.g., upload timeout)  
**Then** the other 2 platforms continue publishing  
**And** the failed platform's `distribution.status` is set to `failed` with `error_message`  
**And** `content.status` remains `rendered` (not all platforms succeeded)

### Requirement: Article Publishing

The system SHALL provide a `publish_article` MCP tool that publishes articles to multiple platforms.

#### Scenario: Publish article to default platforms

**Given** an article exists with slug `finddata-open-data` and status `rendered`  
**When** a user calls `publish_article(slug="finddata-open-data", title="寻数科技")`  
**Then** the system publishes to platforms specified in `.env PLATFORMS_DOCS`  
**And** returns `{results: [{platform, status, url, published_at}]}`  
**And** updates the `distribution` table with results

#### Scenario: Publish article with custom body

**Given** an article exists with slug `finddata-open-data`  
**When** a user calls `publish_article(slug="finddata-open-data", body="...custom content...")`  
**Then** the system uses the provided body instead of reading from `article.md`

### Requirement: Platform Support

The system SHALL support the following platforms.

#### Scenario: Video platforms (6)

**Given** a video is being published  
**Then** the system supports: `douyin`, `xiaohongshu`, `bilibili`, `kuaishou`, `weixin` (视频号), `youtube`

#### Scenario: Article platforms (9)

**Given** an article is being published  
**Then** the system supports: `zhihu`, `weixin` (公众号), `xiaohongshu`, `xueqiu`, `eastmoney`, `tonghuashun`, `toutiao`, `baijiahao`, `weibo`

## Implementation Notes

- Platform-specific scripts remain unchanged (reuse existing `fd-vaas-publish-*` skills)
- MCP server orchestrates via subprocess calls to `publish.mjs`
- DB tracking is new; existing task.json / meta.json remain for backward compatibility
- Error handling: if a platform fails, other platforms continue; partial success is allowed
- Cover generation: `publish_video` auto-generates covers via `fd-cover-image` before publishing (existing behavior)
- Runtime selection: macOS uses ego-browser, Windows uses patchright (auto-detected by `publish.mjs`)
