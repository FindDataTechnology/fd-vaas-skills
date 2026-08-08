"""
Brainstorm tool for structured content planning.

Returns structured JSON templates for voiceover videos or articles.
No external API calls - the LLM reasoning happens in Claude.
"""

from typing import Optional


def brainstorm(
    mode: str,
    topic: str,
    audience: Optional[str] = None,
    brand_context: Optional[dict] = None
) -> dict:
    """
    Generate structured content plan for voiceover or article.

    This tool returns a structured JSON template. The actual content
    generation happens in Claude (the LLM) based on this structure.

    Args:
        mode: Content mode - "voiceover" or "article"
        topic: Main topic/subject
        audience: Target audience description
        brand_context: Optional brand context dict with:
            - company: Company name
            - slogan: Company slogan
            - existing_scripts: List of paths to existing scripts
            - existing_articles: List of paths to existing articles

    Returns:
        Structured JSON template based on mode:

        For voiceover mode:
            - topic_matrix: 5 dimensions with 3-5 topics each
            - script_frameworks: Recommended script structures
            - differentiation_angles: Unique angles per topic
            - full_outline: Complete script outline
            - compliance_check: Platform compliance self-assessment

        For article mode:
            - topic_matrix: 5 dimensions with 3-5 topics each
            - title_options: 3-5 title candidates
            - article_draft: Markdown + plain text versions
            - tags: Platform tags
            - summary: 100-character summary
            - compliance_check: Platform compliance self-assessment

    Raises:
        ValueError: If mode is invalid or topic not provided
    """
    if not topic:
        raise ValueError("topic is required")

    if mode not in ("voiceover", "article"):
        raise ValueError("mode must be 'voiceover' or 'article'")

    if mode == "voiceover":
        return _voiceover_template(topic, audience, brand_context)
    else:
        return _article_template(topic, audience, brand_context)


def _voiceover_template(
    topic: str,
    audience: Optional[str],
    brand_context: Optional[dict]
) -> dict:
    """Return voiceover brainstorm template."""
    return {
        "mode": "voiceover",
        "topic": topic,
        "audience": audience,
        "brand_context": brand_context,
        "topic_matrix": [
            {
                "dimension": "热点型",
                "description": "借势热点、节日、趋势",
                "topics": []  # Claude fills in 3-5 topics
            },
            {
                "dimension": "痛点型",
                "description": "用户真实困扰、焦虑",
                "topics": []
            },
            {
                "dimension": "争议型",
                "description": "反常识、颠覆认知、站队",
                "topics": []
            },
            {
                "dimension": "干货型",
                "description": "方法论、技巧、教程",
                "topics": []
            },
            {
                "dimension": "人设型",
                "description": "个人故事、经历、感悟",
                "topics": []
            }
        ],
        "script_frameworks": [
            {
                "name": "黄金三秒+痛点+方案",
                "structure": "钩子(3s) -> 共情痛点 -> 解决方案 -> 引导",
                "best_for": "通用爆款"
            },
            {
                "name": "SCQA",
                "structure": "情景 -> 冲突 -> 问题 -> 答案",
                "best_for": "知识/观点"
            },
            {
                "name": "PREP",
                "structure": "观点 -> 理由 -> 案例 -> 重申观点",
                "best_for": "说服型"
            }
        ],
        "differentiation_angles": [],  # Claude fills in 2-3 angles
        "full_outline": {
            "hook": "",  # Opening hook (first 3 seconds)
            "body": [],  # Main content points
            "cta": ""  # Call to action (platform-native only)
        },
        "compliance_check": {
            "no_competitor_platforms": None,  # Claude self-assesses
            "no_external_links": None,
            "no_contact_info": None,
            "brand_consistency": None
        }
    }


def _article_template(
    topic: str,
    audience: Optional[str],
    brand_context: Optional[dict]
) -> dict:
    """Return article brainstorm template."""
    return {
        "mode": "article",
        "topic": topic,
        "audience": audience,
        "brand_context": brand_context,
        "topic_matrix": [
            {
                "dimension": "热点型",
                "topics": []
            },
            {
                "dimension": "痛点型",
                "topics": []
            },
            {
                "dimension": "争议型",
                "topics": []
            },
            {
                "dimension": "干货型",
                "topics": []
            },
            {
                "dimension": "人设型",
                "topics": []
            }
        ],
        "title_options": [],  # Claude fills in 3-5 titles
        "article_draft": {
            "markdown_version": "",  # Full markdown article
            "plain_text_version": ""  # Plain text version (no markdown syntax)
        },
        "tags": [],  # 5-8 platform tags
        "summary": "",  # 100-character summary
        "compliance_check": {
            "dual_version_output": None,  # Claude self-assesses
            "no_competitor_platforms": None,
            "no_external_links": None,
            "brand_consistency": None
        }
    }
