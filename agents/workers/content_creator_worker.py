"""
INDRA OS — Content Creator Agent Worker

Turns ideas into content — social media posts, blog articles, images,
and video scripts. Handles platform-specific formatting for Instagram,
LinkedIn, Twitter/X, and blogs.
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.ContentCreator")

CONTENT_DIR = Path("d:/All Projects/My AI Agent/data/content")
CONTENT_DIR.mkdir(parents=True, exist_ok=True)

_STRONG_SIGNALS = [
    "write a post", "create content", "instagram post",
    "linkedin post", "tweet", "blog", "thumbnail",
    "generate image", "create video", "make a reel",
    "write caption", "social media", "content for",
    "write an article", "write a blog", "email template",
    "write copy", "marketing", "ad copy",
    "video script", "podcast script", "newsletter",
]

_MEDIUM_SIGNALS = [
    "post", "content", "write", "create", "draft",
    "caption", "hashtag", "image", "design",
    "story", "reel", "short", "article",
]

# Platform-specific constraints
PLATFORM_RULES = {
    "instagram": {
        "max_chars": 2200,
        "hashtags": 30,
        "format": "Visual-first. Strong opening line. Use emojis. End with CTA. Hashtags at end.",
    },
    "linkedin": {
        "max_chars": 3000,
        "format": "Professional tone. Hook in first line. Use line breaks for readability. End with question/CTA.",
    },
    "twitter": {
        "max_chars": 280,
        "format": "Punchy and concise. Use threads for longer content. 1-2 hashtags max.",
    },
    "blog": {
        "max_chars": 50000,
        "format": "SEO-optimized. H1/H2/H3 structure. Introduction, body with subheadings, conclusion.",
    },
}


class ContentCreatorWorker(BaseAgent):
    """
    Content creation agent. Turns ideas into platform-ready content
    with proper formatting, hashtags, and media generation.
    """

    def __init__(self, llm_func=None, speak_func=None):
        super().__init__(
            name="content_creator",
            description="Create social media posts, articles, images, video scripts, and marketing copy",
            capabilities=[
                "write_post", "write_article", "generate_image_prompt",
                "create_video_script", "create_thumbnail_prompt",
                "write_email", "write_ad_copy", "platform_formatting",
            ],
        )
        self._llm = llm_func
        self._speak = speak_func

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()
        if any(s in lower for s in _STRONG_SIGNALS):
            return 0.93
        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.55
        return 0.05

    async def execute(self, task: Task) -> TaskResult:
        """Create content based on the request."""
        steps_taken = []
        artifacts = []

        try:
            # Classify content type and platform
            content_type, platform = self._classify(task.description)
            steps_taken.append(f"Type: {content_type}, Platform: {platform}")

            if self._speak:
                self._speak(f"Creating {content_type} content, sir.")

            await self.publish_progress(0.1, "Planning content...", 0, 4)

            if content_type == "post":
                return await self._create_post(task, platform, steps_taken)
            elif content_type == "article":
                return await self._create_article(task, steps_taken)
            elif content_type == "video_script":
                return await self._create_video_script(task, steps_taken)
            elif content_type == "email":
                return await self._create_email(task, steps_taken)
            elif content_type == "image_prompt":
                return await self._create_image_prompt(task, steps_taken)
            else:
                return await self._create_generic(task, platform, steps_taken)

        except Exception as e:
            logger.error(f"Content creator error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Content creation failed",
                error=str(e), steps_taken=steps_taken,
            )

    def _classify(self, text: str) -> tuple[str, str]:
        """Classify content type and target platform."""
        lower = text.lower()

        # Platform detection
        platform = "general"
        for p in ["instagram", "linkedin", "twitter", "blog"]:
            if p in lower:
                platform = p
                break

        # Content type
        if any(w in lower for w in ["article", "blog post", "blog"]):
            return "article", platform
        if any(w in lower for w in ["video script", "youtube script", "reel script"]):
            return "video_script", platform
        if any(w in lower for w in ["email", "newsletter"]):
            return "email", platform
        if any(w in lower for w in ["image", "generate image", "picture", "photo"]):
            return "image_prompt", platform
        if any(w in lower for w in ["post", "caption", "tweet"]):
            return "post", platform

        return "post", platform

    async def _create_post(self, task: Task, platform: str, steps: list) -> TaskResult:
        """Create a social media post."""
        if not self._llm:
            return TaskResult(
                task_id=task.id, success=False,
                output="No LLM available", error="No LLM",
                steps_taken=steps,
            )

        rules = PLATFORM_RULES.get(platform, PLATFORM_RULES["instagram"])

        await self.publish_progress(0.3, f"Writing {platform} post...", 1, 4)

        prompt = f"""You are a professional social media content creator.

Create a {platform} post based on this idea:
"{task.description}"

Platform rules:
- Max characters: {rules['max_chars']}
- Format guidelines: {rules['format']}

Return as JSON:
{{
    "post_text": "the full post text with emojis and formatting",
    "hashtags": ["relevant", "hashtags"],
    "image_description": "what image should accompany this post",
    "best_time_to_post": "suggested posting time",
    "engagement_hook": "the key hook/CTA"
}}

JSON:"""

        try:
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            content = json.loads(response)

            await self.publish_progress(0.7, "Formatting output...", 2, 4)

            # Format the final output
            post_text = content.get("post_text", "")
            hashtags = " ".join(f"#{h.strip('#')}" for h in content.get("hashtags", []))
            image_desc = content.get("image_description", "")

            full_output = f"""📱 {platform.upper()} POST
{'='*40}

{post_text}

{hashtags}

{'='*40}
📸 Suggested Image: {image_desc}
⏰ Best Time: {content.get('best_time_to_post', 'N/A')}
🎯 Hook: {content.get('engagement_hook', 'N/A')}
"""

            # Save to file
            filename = f"{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = CONTENT_DIR / filename
            filepath.write_text(full_output, encoding="utf-8")

            await self.publish_progress(1.0, "Done", 4, 4)

            if self._speak:
                self._speak(
                    f"Your {platform} post is ready, sir. "
                    f"Saved to content folder."
                )

            return TaskResult(
                task_id=task.id, success=True,
                output=full_output,
                artifacts=[str(filepath)],
                steps_taken=steps + ["Generated post", "Saved to file"],
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id, success=False,
                output="Failed to create post",
                error=str(e), steps_taken=steps,
            )

    async def _create_article(self, task: Task, steps: list) -> TaskResult:
        """Create a long-form article/blog post."""
        if not self._llm:
            return TaskResult(
                task_id=task.id, success=False,
                output="No LLM", error="No LLM", steps_taken=steps,
            )

        await self.publish_progress(0.2, "Outlining article...", 0, 3)

        # Step 1: Generate outline
        outline_prompt = f"""Create a detailed outline for an article about:
"{task.description}"

Return as JSON:
{{"title": "...", "sections": ["Introduction", "Section 1 Title", "Section 2 Title", "Conclusion"]}}

JSON:"""

        outline_resp = await self._llm(outline_prompt)
        try:
            if "```" in outline_resp:
                outline_resp = outline_resp.split("```")[1].replace("json", "").split("```")[0]
            outline = json.loads(outline_resp)
        except Exception:
            outline = {"title": "Article", "sections": ["Introduction", "Main Content", "Conclusion"]}

        steps.append(f"Outline: {outline.get('title', 'Untitled')}")

        # Step 2: Write full article
        await self.publish_progress(0.5, "Writing article...", 1, 3)

        write_prompt = f"""Write a complete, well-structured article.

Title: {outline.get('title', 'Article')}
Topic: {task.description}
Sections: {json.dumps(outline.get('sections', []))}

Write in markdown format with proper headings, paragraphs, and flow.
Make it engaging, informative, and SEO-friendly.
Target length: 800-1200 words.

Article:"""

        article = await self._llm(write_prompt)

        # Save
        await self.publish_progress(0.9, "Saving...", 2, 3)
        filename = f"article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = CONTENT_DIR / filename
        filepath.write_text(f"# {outline.get('title', 'Article')}\n\n{article}", encoding="utf-8")

        if self._speak:
            self._speak(f"Article written, sir. Title: {outline.get('title', 'Article')}.")

        return TaskResult(
            task_id=task.id, success=True,
            output=f"Article: {outline.get('title', 'Article')}\n\n{article[:500]}...",
            artifacts=[str(filepath)],
            steps_taken=steps + ["Wrote article", "Saved to file"],
        )

    async def _create_video_script(self, task: Task, steps: list) -> TaskResult:
        """Create a video/reel script."""
        if not self._llm:
            return TaskResult(task_id=task.id, success=False, output="No LLM", error="No LLM", steps_taken=steps)

        prompt = f"""Write a video script for:
"{task.description}"

Format:
[SCENE 1 - Description of visual]
NARRATOR: "What to say..."

[SCENE 2 - Description of visual]  
NARRATOR: "What to say..."

Include timing suggestions. Keep it engaging and concise.

Script:"""

        script = await self._llm(prompt)

        filepath = CONTENT_DIR / f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath.write_text(script, encoding="utf-8")

        if self._speak:
            self._speak("Video script ready, sir.")

        return TaskResult(
            task_id=task.id, success=True,
            output=script,
            artifacts=[str(filepath)],
            steps_taken=steps + ["Wrote video script"],
        )

    async def _create_email(self, task: Task, steps: list) -> TaskResult:
        """Write a professional email."""
        if not self._llm:
            return TaskResult(task_id=task.id, success=False, output="No LLM", error="No LLM", steps_taken=steps)

        prompt = f"""Write a professional email for:
"{task.description}"

Return as JSON:
{{"subject": "...", "body": "...", "tone": "formal|casual|friendly"}}

JSON:"""

        response = await self._llm(prompt)
        try:
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            email = json.loads(response)
        except Exception:
            email = {"subject": "Email", "body": response, "tone": "formal"}

        output = f"Subject: {email.get('subject', '')}\n\n{email.get('body', '')}"

        if self._speak:
            self._speak(f"Email drafted, sir. Subject: {email.get('subject', '')}.")

        return TaskResult(
            task_id=task.id, success=True,
            output=output, steps_taken=steps + ["Wrote email"],
        )

    async def _create_image_prompt(self, task: Task, steps: list) -> TaskResult:
        """Generate a detailed image generation prompt."""
        if not self._llm:
            return TaskResult(task_id=task.id, success=False, output="No LLM", error="No LLM", steps_taken=steps)

        prompt = f"""Create a detailed AI image generation prompt for:
"{task.description}"

Return as JSON:
{{
    "prompt": "detailed prompt for Stable Diffusion / DALL-E",
    "negative_prompt": "things to avoid",
    "style": "photorealistic|illustration|3d|anime|oil_painting",
    "aspect_ratio": "1:1|16:9|9:16|4:3"
}}

JSON:"""

        response = await self._llm(prompt)
        try:
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            img_data = json.loads(response)
        except Exception:
            img_data = {"prompt": response, "style": "photorealistic"}

        output = (
            f"🎨 Image Prompt:\n{img_data.get('prompt', '')}\n\n"
            f"❌ Negative: {img_data.get('negative_prompt', 'N/A')}\n"
            f"🖼️ Style: {img_data.get('style', 'N/A')}\n"
            f"📐 Aspect: {img_data.get('aspect_ratio', '1:1')}"
        )

        if self._speak:
            self._speak("Image prompt generated, sir. Ready for Stable Diffusion.")

        return TaskResult(
            task_id=task.id, success=True,
            output=output, steps_taken=steps + ["Generated image prompt"],
        )

    async def _create_generic(self, task: Task, platform: str, steps: list) -> TaskResult:
        """Generic content creation fallback."""
        return await self._create_post(task, platform or "instagram", steps)
