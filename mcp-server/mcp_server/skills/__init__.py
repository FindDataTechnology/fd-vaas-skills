"""Skill modules for VAAS MCP Server.

brainstorm 已从服务端退役（模板知识保留在包根 _brainstorm_knowledge.txt，
后续波次做成 skill）；voiceover 编排由 render_video(type=...) 承担，
skills.voiceover 仅作为 registry video/voiceover 的驱动实现保留。
"""

from .cover import create_cover
from .voiceover import create_voiceover_video
from .publish import publish_video, publish_article
from .query import list_content, get_content

__all__ = [
    "create_cover",
    "create_voiceover_video",
    "publish_video",
    "publish_article",
    "list_content",
    "get_content",
]
