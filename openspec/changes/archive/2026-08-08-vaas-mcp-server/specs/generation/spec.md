# Generation Specification

## Overview

MCP tools for AI-powered content generation: TTS (text-to-speech), image generation, video generation, and cover image generation.

## ADDED Requirements

### Requirement: TTS Generation

The system SHALL provide a `generate_voice` MCP tool that synthesizes speech from text.

#### Scenario: Basic TTS synthesis

**Given** a user provides text input  
**When** they call `generate_voice(text="欢迎使用豆包语音合成")`  
**Then** the system returns `{id, filePath, durationMs}`  
**And** the audio file is saved to `downloads/audio/<slug>/<slug>.mp3`  
**And** a content record is inserted into the DB with `type="audio"`

#### Scenario: TTS with custom voice and speed

**Given** a user provides text, voice, and speed  
**When** they call `generate_voice(text="...", voice="zh_female_gaolengyujie_uranus_bigtts", speed=1.5)`  
**Then** the system uses the specified voice and speed  
**And** returns the same output structure

### Requirement: Image Generation

The system SHALL provide a `generate_image` MCP tool that generates images from text prompts.

#### Scenario: Basic image generation

**Given** a user provides a text prompt  
**When** they call `generate_image(prompt="一只戴着墨镜的橘猫")`  
**Then** the system returns `{id, filePath}`  
**And** the image is saved to `downloads/images/<slug>/<slug>.jpg`  
**And** a content record is inserted into the DB with `type="image"`

#### Scenario: Batch image generation

**Given** a user provides a prompt and batch count  
**When** they call `generate_image(prompt="...", n=3)`  
**Then** the system returns `{id[], filePath[]}` with 3 image paths

### Requirement: Video Generation

The system SHALL provide a `generate_video` MCP tool that generates videos from text prompts.

#### Scenario: Basic video generation

**Given** a user provides a text prompt  
**When** they call `generate_video(prompt="小猫在草地上奔跑")`  
**Then** the system returns `{id, filePath, status}`  
**And** the video is saved to `downloads/videos/<slug>/<slug>.mp4`  
**And** a content record is inserted into the DB with `type="video"`

#### Scenario: Video with custom duration and ratio

**Given** a user provides prompt, duration, and aspect ratio  
**When** they call `generate_video(prompt="...", duration=10, ratio="16:9")`  
**Then** the system generates a 10-second video with 16:9 aspect ratio

### Requirement: Cover Image Generation

The system SHALL provide a `create_cover` MCP tool that generates brand-consistent cover images using Remotion.

#### Scenario: Basic cover generation

**Given** a user provides a title  
**When** they call `create_cover(title="寻数科技")`  
**Then** the system returns `{filePath}`  
**And** the cover is saved to `downloads/images/<slug>/cover-horizontal.jpg` (default 1920x1080)

#### Scenario: Cover with custom orientation and size

**Given** a user provides title, orientation, and size  
**When** they call `create_cover(title="...", orientation="vertical", size="1080x1440")`  
**Then** the system generates a vertical cover with the specified dimensions

## Implementation Notes

- All generators wrap existing scripts via subprocess calls
- TTS: `litellm-bridge.py tts` or direct `_volcengine_tts.py`
- Image: `litellm-bridge.py image` or direct `_volcengine_image.py`
- Video: `litellm-bridge.py video` or direct `_volcengine_video.py`
- Cover: `fd-cover-image/scripts/generate-cover.mjs` (Remotion)
- All outputs are tracked in the `content` table
