# Brainstorm Specification

## Overview

Structured content planning tool that generates topic matrices, script frameworks, and outlines for voiceover videos or articles. Pure prompt-based (no external API calls); the MCP tool returns structured JSON that Claude can use to generate the actual content.

## ADDED Requirements

### Requirement: Voiceover Brainstorm

The system SHALL provide a `brainstorm` MCP tool that generates structured content plans for voiceover videos.

#### Scenario: Basic voiceover brainstorm

**Given** a user provides a topic  
**When** they call `brainstorm(mode="voiceover", topic="职场沟通")`  
**Then** the system returns structured JSON with:
- `topic_matrix[]` — 5 dimensions (热点型/痛点型/争议型/干货型/人设型), each with 3-5 topics
- `script_frameworks[]` — recommended script structures (黄金三秒+痛点+方案, SCQA, PREP, etc.)
- `differentiation_angles[]` — 2-3 unique angles per topic
- `full_outline` — complete script outline for the strongest topic (hook, body, CTA)
- `compliance_check` — self-assessment of platform compliance (no competitor names, no external links)

#### Scenario: Voiceover brainstorm with audience

**Given** a user provides topic and audience  
**When** they call `brainstorm(mode="voiceover", topic="职场沟通", audience="内向者")`  
**Then** the system tailors the output to the specified audience

#### Scenario: Voiceover brainstorm with brand context

**Given** a user provides brand context  
**When** they call `brainstorm(mode="voiceover", topic="...", brand_context={company="寻数科技", slogan="..."})`  
**Then** the system ensures brand consistency in the output  
**And** `compliance_check.brand_consistency` is `true`

### Requirement: Article Brainstorm

The system SHALL provide a `brainstorm` MCP tool that generates structured content plans for articles.

#### Scenario: Basic article brainstorm

**Given** a user provides a topic  
**When** they call `brainstorm(mode="article", topic="AI工具")`  
**Then** the system returns structured JSON with:
- `topic_matrix[]` — 5 dimensions, each with 3-5 topics
- `title_options[]` — 3-5 title candidates (提问式/数字式/悬念式/价值式)
- `article_draft` — complete article with both `markdown_version` and `plain_text_version`
- `tags[]` — 5-8 tags for platform distribution
- `summary` — 100-character summary
- `compliance_check` — self-assessment of dual-version output and platform compliance

#### Scenario: Article brainstorm with audience

**Given** a user provides topic and audience  
**When** they call `brainstorm(mode="article", topic="AI工具", audience="程序员")`  
**Then** the system tailors the output to the specified audience

### Requirement: Compliance Rules

The system SHALL enforce platform compliance rules for all brainstorm output.

#### Scenario: Voiceover compliance

**Given** a voiceover brainstorm is generated  
**Then** the output must pass:
- No competitor platform names (抖音/B站/小红书/知乎/公众号/微信/微博/快手/视频号)
- No external links or QR codes
- No contact information (phone/WeChat/QQ/email)
- CTA uses only platform-native actions (点赞/关注/收藏/评论/转发)

#### Scenario: Article compliance

**Given** an article brainstorm is generated  
**Then** the output must pass:
- Dual-version output (Markdown + plain text)
- No competitor platform names
- No external links
- Brand consistency (if brand_context provided)

## Implementation Notes

- No external API calls; the MCP tool returns structured JSON
- Claude (the LLM) fills in the actual content based on the structure
- Brand context is optional but recommended for consistency
- Compliance check is a self-assessment by Claude, not an external validation
- Output can be directly used by `create_voiceover_video` (voiceover mode) or `publish_article` (article mode)
- Brainstorm output is transient (not persisted to DB)
