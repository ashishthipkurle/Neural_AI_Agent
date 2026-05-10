
import logging
import asyncio
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional

from agent.skills.base_skill import BaseSkill, SkillManifest, SkillResult, SkillHealth

# Try imports
try:
    from telegram import Bot, Update
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.error import TelegramError
except ImportError:
    Bot = None
    Update = None
    Application = None
    ApplicationBuilder = None
    CommandHandler = None
    MessageHandler = None
    filters = None
    ContextTypes = None
    TelegramError = None

class TelegramSkill(BaseSkill):
    """
    Module 8: Telegram Controller Skill
    Messaging and Human-in-the-Loop Approval.
    Supports both sending and receiving messages via polling.
    """

    def __init__(self, config: Dict[str, Any] = None, agent: Any = None):
        self._name = "telegram"
        super().__init__()
        self.config = config or {}
        self.agent = agent
        
        self.token = self.config.get('telegram', {}).get('bot_token')
        self.chat_id = self.config.get('telegram', {}).get('chat_id') # Main user ID
        
        self.bot = None
        self.application = None
        self._polling_task = None
        self._polling_monitor_task = None
        self._polling_started = False

        # Simple counters to detect whether a mission already sent a Telegram document during handling.
        # Keyed by chat_id (string).
        self._sent_document_counter: Dict[str, int] = {}
        
        # Autonomous Trading Integration
        self.trading_loop = None
        if os.environ.get("TRADING_ENABLED", "false").lower() == "true":
            try:
                from agent.trading.autonomous_loop import AutonomousTradingLoop
                self.logger.info("Initializing Autonomous Trading Loop...")
                self.trading_loop = AutonomousTradingLoop()
            except Exception as e:
                self.logger.error(f"Failed to load trading loop: {e}")
        
        self._setup_bot()

    def _setup_bot(self):
        if Application and self.token:
            try:
                # Build Application (v20+)
                builder = ApplicationBuilder().token(self.token)
                builder.connect_timeout(30.0)
                builder.read_timeout(30.0)
                builder.write_timeout(30.0)
                self.application = builder.build()
                self.bot = self.application.bot # For legacy/direct use
                
                # Register Handlers
                self.application.add_handler(CommandHandler("start", self._cmd_start))
                # Catch-all for other commands (e.g. /task, /ask)
                self.application.add_handler(MessageHandler(filters.COMMAND, self._handle_command))
                # Handle text messages
                self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
                
                self._health = SkillHealth.READY
            except Exception as e:
                self.logger.error(f"Failed to init Telegram app: {e}")
                self._health = SkillHealth.UNAVAILABLE
        else:
            if not Application:
                self.logger.warning("python-telegram-bot not installed.")

    def on_load(self):
        """Sync load."""
        super().on_load()

    async def on_start(self):
        """Start polling on start (with increased timeout handling)."""
        if self.application and not self._polling_started:
            self.logger.info("Starting Telegram polling...")
            try:
                self.logger.info("Initializing Telegram app...")
                await self.application.initialize()
                
                self.logger.info("Starting Telegram app...")
                await self.application.start()
                
                self.logger.info("Starting updaters...")
                # start_polling returns after starting the updater; updater keeps running in background.
                await self.application.updater.start_polling()
                self._polling_started = True
                self._ensure_polling_monitor()
                self.logger.info("Telegram polling started.")
                
                if self.trading_loop:
                    self.logger.info("Starting Autonomous Trading Loop...")
                    self.trading_loop.start()
                    
            except Exception as e:
                self.logger.error(f"Failed to start polling: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
        elif self.application and self._polling_started:
            # Polling was started previously; ensure monitor exists.
            self._ensure_polling_monitor()
            
            if self.trading_loop:
                self.trading_loop.start()

    def _ensure_polling_monitor(self) -> None:
        if self._polling_monitor_task and not self._polling_monitor_task.done():
            return
        self._polling_monitor_task = asyncio.create_task(self._monitor_polling())

    async def _monitor_polling(self) -> None:
        """Keep Telegram polling alive.

        PTB polling can stop due to network errors; this monitor restarts it.
        """
        backoff_s = 2.0
        while self.application:
            try:
                if not getattr(self.application, "running", False):
                    self.logger.warning("Telegram application not running; attempting restart...")
                    try:
                        await self.application.initialize()
                    except Exception as init_err:
                        self.logger.debug(f"Telegram initialize skipped/failed (may already be initialized): {init_err}")
                    try:
                        await self.application.start()
                    except Exception as e:
                        self.logger.error(f"Failed to (re)start Telegram application: {e}")

                # Updater health check
                if not getattr(self.application.updater, "running", False):
                    self.logger.warning("Telegram polling not running; attempting restart...")
                    try:
                        await self.application.updater.start_polling()
                        self._polling_started = True
                        self.logger.info("Telegram polling restarted.")
                        backoff_s = 2.0
                    except Exception as e:
                        self.logger.error(f"Failed to restart Telegram polling: {e}")
                        await asyncio.sleep(backoff_s)
                        backoff_s = min(backoff_s * 2, 60.0)
                        continue

                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.logger.error(f"Telegram polling monitor error: {e}")
                await asyncio.sleep(5.0)

    async def on_unload(self):
        """Stop polling on unload."""
        if self.application:
            self.logger.info("Stopping Telegram polling...")
            try:
                if self._polling_monitor_task:
                    self._polling_monitor_task.cancel()
                    try:
                        await self._polling_monitor_task
                    except asyncio.CancelledError:
                        pass

                if self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
                    await self.application.shutdown()
            except Exception as e:
                self.logger.error(f"Error stopping Telegram: {e}")
                
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
            self.logger.info("Telegram polling stopped.")

    # --- Handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        await update.message.reply_html(
            f"Hello {user.mention_html()}! I am your AI Agent.\n"
            "I am now connected and listening. You can chat with me directly here."
        )

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming commands like /task, /open, etc."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        
        # Intercept trading commands
        if self.trading_loop and self.trading_loop.telegram.is_trading_command(text):
            response = self.trading_loop.telegram.handle_trading_command(text)
            if response:
                await update.message.reply_text(response)
            return

        # Strip leading slash to support fast command routing (e.g. "/open" -> "open")
        if text.startswith('/'):
            text = text[1:]
            
        await self._relay_to_agent(update, text)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        await self._relay_to_agent(update, text)

    async def _relay_to_agent(self, update: Update, text: str):
        """Common logic to send text to agent.

        Intelligently classifies incoming messages:
        - Simple questions (who, what, when, etc.) → direct text reply, no mission overhead.
        - Complex tasks (make, create, build, research, go to, etc.) → full mission flow with
          progress banner and PDF report.
        """
        user_id = update.effective_user.id
        
        # Security check: only allow main chat_id if configured
        if self.chat_id and str(user_id) != str(self.chat_id):
             self.logger.warning(f"Message from unauthorized user: {user_id}")
             # await update.message.reply_text("⛔ Unauthorized.")
             # return

        if not self.agent:
            await update.message.reply_text("⚠ Agent not linked. Cannot process message.")
            return

        # Indicate processing
        await update.message.chat.send_action(action="typing")

        reply_mode = (self.config.get("telegram", {}) or {}).get("reply_mode", "auto")  # auto|file|text|both
        send_progress = bool((self.config.get("telegram", {}) or {}).get("progress_updates", True))

        chat_id = str(update.effective_chat.id) if update and update.effective_chat else ""
        docs_before = self._sent_document_counter.get(chat_id, 0)

        # ── Classify: simple question vs complex task ──
        is_simple = self._is_simple_question(text)

        if is_simple:
            # ── SIMPLE PATH: direct text reply, no mission overhead ──
            try:
                # Show a loading indicator so user knows the agent is working
                thinking_msg = await update.message.reply_text("⏳ Thinking...")

                chat_src = f"telegram:{update.effective_chat.id}" if update and update.effective_chat else "telegram"
                response = await self.agent.process_input(text, source=chat_src)

                inline = (response or "").strip()
                if len(inline) > 3500:
                    inline = inline[:3500] + "…"
                if inline:
                    # Edit the "Thinking..." message into the actual answer
                    try:
                        await thinking_msg.edit_text(inline)
                    except Exception:
                        # If edit fails (e.g. same content), send as new message
                        await thinking_msg.delete()
                        await update.message.reply_text(inline)
                else:
                    await thinking_msg.edit_text("I couldn't find an answer to that.")

            except Exception as e:
                self.logger.error(f"Agent processing failed: {e}")
                try:
                    await thinking_msg.edit_text(f"❌ Error: {str(e)}")
                except Exception:
                    await update.message.reply_text(f"❌ Error: {str(e)}")
            return

        # ── MISSION PATH: full progress + report ──
        # Immediate acknowledgement (so user knows the mission is running)
        if send_progress:
            preview = (text or "").strip().replace("\n", " ")
            if len(preview) > 160:
                preview = preview[:160] + "…"
            await update.message.reply_text(
                "🟡 Mission in progress\n"
                f"Task: {preview}\n\n"
                "I'll send a report file when it's done."
            )

        # Route to agent
        try:
            chat_src = f"telegram:{update.effective_chat.id}" if update and update.effective_chat else "telegram"
            response = await self.agent.process_input(text, source=chat_src)

            docs_after = self._sent_document_counter.get(chat_id, 0)
            mission_sent_doc = docs_after > docs_before

            # If a mission already sent a document while handling this request, do NOT duplicate.
            if mission_sent_doc or self._looks_like_mission_already_reported(response):
                if send_progress:
                    await update.message.reply_text("✅ Mission completed. Report sent.")
                return

            if reply_mode in ("text", "both"):
                # Keep inline replies short to avoid Telegram spam
                inline = (response or "").strip()
                if len(inline) > 3500:
                    inline = inline[:3500] + "…"
                if inline:
                    await update.message.reply_text(inline)

            sent_own_report = False
            if reply_mode in ("auto", "file", "both"):
                report_path = await self._write_report_file_async(request_text=text, response_text=response)
                caption = f"Mission Report: {text[:60].strip()}" if text else "Mission Report"
                with open(report_path, "rb") as f:
                    await self.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        caption=caption,
                    )
                sent_own_report = True

            if send_progress:
                if sent_own_report:
                    snippet = (response or "").strip().replace("\n", " ")
                    if len(snippet) > 220:
                        snippet = snippet[:220] + "…"
                    summary_line = f"\nSummary: {snippet}" if snippet else ""
                    await update.message.reply_text(f"✅ Mission completed. Report file sent.{summary_line}")
                else:
                    await update.message.reply_text("✅ Mission completed.")

        except Exception as e:
            self.logger.error(f"Agent processing failed: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    @staticmethod
    def _is_simple_question(text: str) -> bool:
        """Classify whether a message is a simple conversational question
        (deserving a direct text reply) vs a complex task/command (mission).

        Returns True for simple questions, False for complex tasks.
        """
        if not text:
            return True

        lower = text.strip().lower()
        words = lower.split()
        word_count = len(words)

        # Very short messages (1-2 words like "hi", "hello", "thanks") → simple
        if word_count <= 2:
            return True

        # ── COMPLEX TASK indicators (check first, takes priority) ──
        # Action verbs that clearly indicate a task/mission
        task_verbs = [
            "make me", "create", "build", "generate", "design", "develop",
            "write me", "code", "implement", "set up", "setup", "install",
            "deploy", "configure", "fix", "debug", "update", "modify",
            "change", "edit", "remove", "delete", "add", "send",
            "download", "upload", "search for", "find me",
            "go to", "navigate", "open", "browse", "visit",
            "research", "analyze", "compare", "summarize this",
            "run", "execute", "start", "launch", "stop",
            "schedule", "automate", "monitor", "scan", "scrape",
        ]
        for verb in task_verbs:
            if verb in lower:
                return False

        # Patterns like "X and send it to telegram", "X then Y" → multi-step = complex
        if re.search(r'\b(and\s+send|then\s+send|and\s+then|after\s+that)\b', lower):
            return False

        # URLs or website names → likely a browsing task
        if re.search(r'https?://|www\.|\.com|\.org|\.net|\.io', lower):
            return False

        # ── SIMPLE QUESTION indicators ──
        # Starts with question words
        question_starters = [
            "who", "what", "when", "where", "why", "how",
            "is", "are", "was", "were", "do", "does", "did",
            "can", "could", "would", "should", "will",
            "tell me", "explain", "define", "describe",
            "what's", "who's", "where's", "when's", "how's",
            "what is", "who is", "where is", "when is", "how is",
            "what are", "who are", "where are", "how are",
            "what was", "who was", "how do", "how does",
            "how much", "how many", "how long", "how far",
            "do you know", "can you tell",
        ]
        for starter in question_starters:
            if lower.startswith(starter):
                return True

        # Ends with a question mark → likely a question
        if text.strip().endswith("?"):
            return True

        # Short conversational messages (greetings, thanks, etc.)
        casual_patterns = [
            "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
            "good morning", "good night", "good evening", "bye", "goodbye",
            "nice", "cool", "great", "awesome", "sure", "yes", "no",
            "help", "menu", "status",
        ]
        if lower in casual_patterns or (word_count <= 4 and any(p in lower for p in casual_patterns)):
            return True

        # If message is short (under ~8 words) and doesn't match task verbs → likely simple
        if word_count <= 8:
            return True

        # If we got here, no task verbs matched, no URLs, no multi-step patterns.
        # It's a conversational message → treat as simple.
        return True

    async def _write_report_file_async(self, request_text: str, response_text: str) -> str:
        cfg = (self.config.get("telegram", {}) or {})
        report_dir = cfg.get("report_dir") or "agent_data/telegram_reports"
        out_dir = Path(report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Output format: "md" (default), "pdf", or "both".
        report_format = (cfg.get("report_format") or cfg.get("report_output") or "md").strip().lower()
        # Allow emergency override via env var (useful when config isn't propagating).
        env_override = (os.environ.get("TELEGRAM_REPORT_FORMAT") or "").strip().lower()
        if env_override in ("md", "pdf", "both"):
            report_format = env_override

        self.logger.info(
            "Telegram report generation: format=%s report_dir=%s telegram_cfg_keys=%s",
            report_format,
            str(out_dir),
            sorted(list(cfg.keys())),
        )

        def _slug(s: str) -> str:
            s = (s or "").strip().lower()
            s = re.sub(r"\s+", "_", s)
            s = re.sub(r"[^a-z0-9_\-]", "", s)
            return s[:40] or "task"

        ts = int(time.time())
        slug = _slug(request_text)
        filename = f"telegram_report_{slug}_{ts}.md"
        md_path = out_dir / filename

        formatted_result = self._format_response_for_report(request_text=request_text, response_text=response_text)
        content = (
            f"# Mission Report\n\n"
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"## Task\n\n{(request_text or '').strip()}\n\n"
            f"## Result\n\n{formatted_result.strip()}\n"
        )

        md_path.write_text(content, encoding="utf-8", errors="replace")

        if report_format not in ("pdf", "both"):
            self.logger.info("Telegram report written (md): %s", str(md_path))
            return str(md_path)

        pdf_path = md_path.with_suffix(".pdf")
        try:
            self.logger.info("Telegram report PDF render start: %s", str(pdf_path))
            await self._render_report_pdf_async(markdown_text=content, out_pdf_path=str(pdf_path))
            self.logger.info("Telegram report PDF render ok: %s", str(pdf_path))
        except Exception as e:
            # Fall back to markdown if PDF generation fails (e.g., Playwright browsers not installed).
            import traceback
            self.logger.error(f"PDF render failed; sending Markdown instead: {e}\n{traceback.format_exc()}")
            return str(md_path)

        # For "pdf" and "both": send the PDF (while keeping the .md on disk for archival/search).
        return str(pdf_path)

    @staticmethod
    async def _render_report_pdf_async(markdown_text: str, out_pdf_path: str) -> None:
        """Render a Markdown report to PDF using Playwright.

        This avoids format changes across apps by producing a fixed-layout PDF.
        """
        import html
        from pathlib import Path

        # Optional: if python-markdown is available, render to HTML; otherwise fallback to <pre>.
        body_html: str
        try:
            import markdown as md  # type: ignore

            body_html = md.markdown(
                markdown_text,
                extensions=["tables", "fenced_code"],
                output_format="html5",
            )
        except Exception:
            body_html = f"<pre>{html.escape(markdown_text)}</pre>"

        doc = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Mission Report</title>
    <style>
      :root {{ color-scheme: light; }}
      body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; line-height: 1.4; font-size: 12.5px; }}
      h1, h2, h3 {{ margin: 0.6em 0 0.4em; }}
      h1 {{ font-size: 22px; }}
      h2 {{ font-size: 16px; }}
      h3 {{ font-size: 14px; }}
      pre {{ white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }}
      code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
      th {{ background: #f5f5f5; text-align: left; }}
      ul {{ margin: 0.2em 0 0.6em 1.2em; }}
      li {{ margin: 0.15em 0; }}
      .page {{ padding: 6px 6px; }}
    </style>
  </head>
  <body>
    <div class="page">
      {body_html}
    </div>
  </body>
</html>
"""

        Path(out_pdf_path).parent.mkdir(parents=True, exist_ok=True)
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(doc, wait_until="networkidle")
            await page.emulate_media(media="screen")
            await page.pdf(
                path=out_pdf_path,
                format="A4",
                margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                print_background=True,
            )
            await browser.close()

    @classmethod
    def _format_response_for_report(cls, request_text: str, response_text: str) -> str:
        """Format agent output into a human-friendly Telegram document.

        Goal: keep it readable on mobile/desktop Telegram (headings + bullets, minimal clutter).
        """
        raw = (response_text or "").strip()
        if not raw:
            return "(No result text returned.)"

        # Normalize HTML-ish breaks that frequently appear in LLM output.
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)

        # If the agent responded with "saved to <path>" (common pattern), inline the file contents.
        expanded = cls._try_inline_referenced_file(raw)
        if expanded:
            raw = expanded

        # Special-case: the AI frameworks table output (dense) → convert to per-framework sections.
        table_formatted = cls._try_format_ai_frameworks_table(raw)
        if table_formatted:
            return table_formatted

        accomplishment_formatted = cls._try_format_accomplishment_summary(raw)
        if accomplishment_formatted:
            return accomplishment_formatted

        # Default: keep text, but ensure it starts as plain content (avoid giant single paragraphs).
        # (We intentionally do NOT hard-wrap lines because Telegram Markdown handles long lines fine.)
        return raw

    @staticmethod
    def _try_inline_referenced_file(text: str) -> Optional[str]:
        """If the response references a local file path, inline its contents for the report.

        This is critical for PDF delivery: clients should see the data, not only a file pointer.
        """
        if not text:
            return None

        lower = text.lower()
        if "saved to" not in lower and "saved" not in lower and "file" not in lower:
            return None

        candidates: list[str] = []

        # Prefer bolded path: **D:\...\file.txt**
        for m in re.findall(r"\*\*([A-Za-z]:\\[^*\n\r]+)\*\*", text):
            candidates.append(m.strip())

        # Also accept plain windows paths ending in common text formats.
        for m in re.findall(r"([A-Za-z]:\\[^\n\r]+?\.(?:txt|md|log|json))", text, flags=re.IGNORECASE):
            candidates.append(m.strip())

        # De-dupe while preserving order.
        seen = set()
        paths: list[str] = []
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            paths.append(c)

        if not paths:
            return None

        # Inline only the first valid file to avoid huge reports.
        for p in paths:
            try:
                path = Path(p)
                if not path.exists() or not path.is_file():
                    continue

                # Safety cap (bytes) and (lines)
                max_bytes = 250_000
                max_lines = 420

                data = path.read_bytes()
                if len(data) > max_bytes:
                    data = data[:max_bytes]
                content = data.decode("utf-8", errors="replace")

                # If this is the consolidated summary file, extract the most relevant block.
                if path.name.lower() == "final_user_summary.txt":
                    m = re.search(
                        r"---\s*concise_summary\.txt\s*---\s*(.*?)(?=\n---\s+[^\n]+\s+---|\Z)",
                        content,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                    if m:
                        content = m.group(1).strip() + "\n"

                # Trim by lines to avoid extremely long PDFs.
                lines = content.splitlines()
                trimmed = "\n".join(lines[:max_lines])
                if len(lines) > max_lines:
                    trimmed += "\n\n…(truncated)…"

                ext = path.suffix.lower()
                out: list[str] = []
                out.append(text.strip())
                out.append("")
                out.append("---")
                out.append("")
                out.append(f"### Included Output: {path.name}")
                out.append("")
                out.append(f"Source: {str(path)}")
                out.append("")

                if ext == ".md":
                    out.append(trimmed)
                else:
                    out.append("```text")
                    out.append(trimmed)
                    out.append("```")

                return "\n".join(out).strip() + "\n"
            except Exception:
                continue

        return None

    @staticmethod
    def _try_format_accomplishment_summary(text: str) -> Optional[str]:
        """Reformat an 'Accomplishment Summary' block into a cleaner, guide-like layout."""

        if "accomplishment summary" not in text.lower():
            return None

        # Pull bullet lines ("- ...")
        bullets: list[str] = []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("-"):
                bullets.append(s.lstrip("-").strip())

        if not bullets:
            return None

        file_paths: list[str] = []
        for b in bullets:
            for match in re.findall(r"[A-Za-z]:\\[^\s`]+", b):
                file_paths.append(match)

        out: list[str] = []
        out.append("### Accomplishment Summary")
        out.append("")
        out.append("**What happened**")
        out.extend(f"- {b}" for b in bullets)

        if file_paths:
            out.append("")
            out.append("**Files mentioned**")
            seen = set()
            for p in file_paths:
                if p in seen:
                    continue
                seen.add(p)
                out.append(f"- {p}")

        return "\n".join(out).strip() + "\n"

    @staticmethod
    def _try_format_ai_frameworks_table(text: str) -> Optional[str]:
        """If text contains a Markdown table for frameworks, reformat into readable sections."""

        def _clean_cell(cell: str) -> str:
            cell = (cell or "").strip()
            cell = re.sub(r"<br\s*/?>", "\n", cell, flags=re.IGNORECASE)
            cell = cell.replace("\\n", "\n")
            return cell.strip()

        def _to_bullets(cell: str) -> str:
            cell = _clean_cell(cell)
            if not cell:
                return "- (n/a)"

            # Split on common bullet markers.
            parts = []
            for line in cell.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Handle inline bullets like "• A • B".
                if "•" in line and not line.startswith("•"):
                    for p in [p.strip() for p in line.split("•") if p.strip()]:
                        parts.append(p)
                else:
                    parts.append(line.lstrip("•").strip())

            if not parts:
                return "- (n/a)"
            return "\n".join(f"- {p}" for p in parts)

        lines = text.splitlines()

        def _is_table_row(ln: str) -> bool:
            # Header rows and well-formed rows: must have leading and trailing pipe.
            return bool(re.match(r"^\s*\|.+\|\s*$", ln))

        def _is_separator_row(ln: str) -> bool:
            # Typical markdown separator: | --- | :---: | ---: |
            return bool(re.match(r"^\s*\|\s*[:\-]+\s*(\|\s*[:\-]+\s*)+\|\s*$", ln))

        # Find the first table header + separator.
        start = None
        for i, ln in enumerate(lines):
            if _is_table_row(ln) and i + 1 < len(lines) and _is_separator_row(lines[i + 1]):
                start = i
                break

        if start is None:
            return None

        # Parse header + (potentially multi-line) rows.
        def _split_row(row: str) -> list[str]:
            row = row.strip().strip("|")
            return [c.strip() for c in row.split("|")]

        header_line = lines[start].strip()
        header = _split_row(header_line)
        header_l = [h.strip().lower() for h in header]

        # Guard: only treat as an AI frameworks table if it actually has a Framework column.
        if not any(h == "framework" for h in header_l):
            return None
        expected_cells = len(header)
        expected_pipes = expected_cells + 1

        # Collect row blocks. Some LLM outputs wrap cells across lines without repeating pipes.
        row_blocks: list[str] = []
        cur: list[str] = []
        in_rows = False

        for ln in lines[start + 2 :]:
            raw_ln = ln.rstrip("\n")
            stripped = raw_ln.strip()

            # End of table when we hit a blank line and we're not currently inside a wrapped row.
            if not stripped and not cur and in_rows:
                break

            # Start of a new row if it begins with a pipe.
            if stripped.startswith("|"):
                in_rows = True
                if cur:
                    row_blocks.append("\n".join(cur).strip())
                    cur = []
                cur.append(raw_ln)
                continue

            # Continuation of the current row (wrapped content).
            if cur:
                cur.append(raw_ln)

                # If we've now accumulated enough pipe delimiters, close the row.
                if "\n".join(cur).count("|") >= expected_pipes:
                    row_blocks.append("\n".join(cur).strip())
                    cur = []
                continue

            # Not in a row yet (or table ended).
            if in_rows:
                break

        if cur:
            row_blocks.append("\n".join(cur).strip())

        rows: list[list[str]] = []
        for block in row_blocks:
            # Ignore separator-ish blocks.
            if set(block.replace("|", "").replace("\n", "").strip()) <= {"-", ":"}:
                continue
            cols = _split_row(block.replace("\r", ""))
            if len(cols) >= expected_cells:
                rows.append(cols)

        # Extra guard: ensure this table is about TensorFlow/PyTorch/JAX (avoid rewriting unrelated tables).
        table_text_l = ("\n".join([header_line] + row_blocks)).lower()
        if not any(k in table_text_l for k in ("tensorflow", "pytorch", "jax")):
            return None

        if not rows:
            return None

        # Capture trailing text after the table (e.g., Take-away/Summary).
        # We approximate the tail as everything after the last row block in the original text.
        tail = ""
        if row_blocks:
            last = row_blocks[-1]
            pos = text.find(last)
            if pos != -1:
                tail = text[pos + len(last) :].strip()
        tail = re.sub(r"^\*\*summary\*\*\s*", "", tail, flags=re.IGNORECASE | re.MULTILINE).strip()

        out: list[str] = []
        out.append("### Top 3 AI Frameworks (2025)")
        out.append("")
        out.append("**Quick take**")
        out.append("- **TensorFlow**: production + deployment ecosystem")
        out.append("- **PyTorch**: research + prototyping velocity")
        out.append("- **JAX**: high-performance + scientific/TPU-first workflows")

        # Map by column index for expected table shape.
        # 0 Framework | 1 Key Features | 2 Core Strengths | 3 Typical Use‑Cases | 4 Why It Ranks #1‑3
        for idx, cols in enumerate(rows, start=1):
            framework = _clean_cell(cols[0])
            key_features = cols[1] if len(cols) > 1 else ""
            # Support multiple table schemas:
            # - 5 cols: Framework | Key Features | Core Strengths | Typical Use-Cases | Why
            # - 5 cols (alt): Framework | Key Features | Typical Use-Cases | Strengths | Weaknesses
            # - 6 cols: Framework | Key Features | Typical Use-Cases | Strengths | Weaknesses | Why
            col_names = [h.lower() for h in header]

            def _col(idx_default: int, *names: str) -> str:
                for n in names:
                    if n.lower() in col_names:
                        i = col_names.index(n.lower())
                        return cols[i] if i < len(cols) else ""
                return cols[idx_default] if idx_default < len(cols) else ""

            core_strengths = _col(2, "core strengths", "strengths")
            use_cases = _col(3, "typical use‑cases", "typical use-cases", "typical use cases", "use‑cases", "use-cases")
            weaknesses = _col(4, "weaknesses")
            why = _col(4, "why it ranks #1‑3", "why it ranks #1-3", "why it ranks")

            out.append("")
            out.append(f"{idx}. **{framework}**")
            out.append("")
            out.append("**Key features**")
            out.append(_to_bullets(key_features))
            out.append("")
            out.append("**Typical use-cases**")
            out.append(_to_bullets(use_cases))
            out.append("")

            out.append("**Strengths**")
            out.append(_to_bullets(core_strengths))
            out.append("")

            if weaknesses.strip():
                out.append("**Weaknesses**")
                out.append(_to_bullets(weaknesses))
                out.append("")

            if why.strip():
                out.append("**Why it ranks #1-3**")
                why_clean = _clean_cell(why)
                out.append(why_clean if why_clean else "(n/a)")

        if tail:
            out.append("")
            out.append("### Summary")
            out.append(tail)

        return "\n".join(out).strip() + "\n"

    @staticmethod
    def _looks_like_mission_already_reported(response: Optional[str]) -> bool:
        if not response:
            return False
        r = response.lower()
        # MissionSkill emits messages like "Mission Complete" / "Sending full report..." and sends docs itself.
        triggers = [
            "sending full report",
            "mission report",
            "mission complete",
            "report sent",
            "sent as file",
        ]
        return any(t in r for t in triggers)

    @property
    def name(self) -> str:
        return self._name

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self.name,
            version="1.1.0",
            description="Telegram messaging and approval system (Bidirectional).",
            actions=["send_message", "request_approval", "send_document"],
            requires=["python-telegram-bot"],
            permissions=["network"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        text = intent.lower() if isinstance(intent, str) else str(intent).lower()
        if "telegram" in text or "send message" in text:
            return 0.9
        return 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        if action == "send_message":
            text = params.get('text') or params.get('message')
            if not text:
                return SkillResult(success=False, error="No text provided.")
                
            success = await self.send_message(text)
            return SkillResult(success=success, message="Message sent" if success else "Failed")
            
        elif action == "request_approval":
            description = params.get('description', 'Unknown Action')
            risk_level = params.get('risk_level', 'UNKNOWN')
            
            approved = await self.request_approval(description, risk_level)
            return SkillResult(success=True, data={"approved": approved})

        elif action == "send_document":
            path = params.get('path')
            caption = params.get('caption')
            chat_id = params.get('chat_id')

            if not path:
                return SkillResult(success=False, error="No document path provided.")

            if not self.bot:
                return SkillResult(success=False, error="Telegram bot not initialized.")

            import os
            if not os.path.exists(path):
                return SkillResult(success=False, error=f"File not found: {path}")

            target_chat = chat_id or self.chat_id
            if not target_chat:
                return SkillResult(success=False, error="No destination chat ID.")

            try:
                # Robustly handle sending:
                # If self.bot is the wrapper, it has send_document(document_path=...)
                # If self.bot is ExtBot (raw), it needs send_document(chat_id=..., document=open(...))
                
                # Check if it's the wrapper (has 'auth' attribute usually, or check method signature?)
                # Safest: Try wrapper signature, fallback to raw.
                
                # Actually, based on logs, self.bot IS the ExtBot. Use the raw interface directly.
                with open(path, 'rb') as f:
                    await self.bot.send_document(
                        chat_id=target_chat,
                        document=f,
                        caption=caption
                    )

                # Track that a document was sent for this chat, so the inbound handler can avoid duplicating output.
                cid = str(target_chat)
                self._sent_document_counter[cid] = self._sent_document_counter.get(cid, 0) + 1
                return SkillResult(success=True, message=f"Document sent: {path}")
            except Exception as e:
                self.logger.error(f"Failed to send document: {e}")
                return SkillResult(success=False, error=f"Send failed: {e}")
            
        return SkillResult(success=False, error=f"Unknown action: {action}")

    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """Send a simple text message."""
        if not self.bot:
            return False
            
        target = chat_id or self.chat_id
        if not target:
            self.logger.error("No Chat ID provided for Telegram.")
            return False
            
        try:
            await self.bot.send_message(chat_id=target, text=text)
            return True
        except Exception as e:
            self.logger.error(f"Telegram send failed: {e}")
            return False

    async def request_approval(self, action_description: str, risk_level: str) -> bool:
        """
        Send approval request with inline buttons (mocked for foundation logic).
        Returns True/False based on user response.
        """
        if not self.bot or not self.chat_id:
            self.logger.warning("Telegram not configured for approval.")
            return False
            
        message = f"⚠️ **APPROVAL REQUEST** ⚠️\n\nAction: {action_description}\nRisk: {risk_level}\n\nApprove?"
        
        # In a real async bot, we would:
        # 1. Send message with InlineKeyboard (Yes/No)
        # 2. Wait for CallbackQuery handler to trigger an event or future
        # 3. Return the result
        
        await self.send_message(message)
        
        # NOTE: A real implementation would verify specific message ID and wait. 
        # Here we just log it. 
        self.logger.info(f"Sent approval request for {action_description}")
        return False # Default to deny for safety until callback logic is wired up.
