"""
Workflow Node Executors — Real implementations for each workflow node type.

Each executor takes an input dict (from previous node or trigger data)
and returns an output dict to pass to the next node.
"""

import asyncio
import json
import logging
import os
import smtplib
import imaplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable

logger = logging.getLogger("WorkflowExecutors")


class BaseExecutor:
    """Base class for all workflow node executors."""

    node_type: str = "unknown"

    async def execute(self, node_config: Dict[str, Any], input_data: Dict[str, Any],
                      broadcast: Callable = None) -> Dict[str, Any]:
        """
        Execute this node.

        Args:
            node_config: The node's configuration (label, params, etc.)
            input_data: Output from the previous node(s)
            broadcast: Optional callback to send status updates

        Returns:
            Output data dict to pass to next node(s)
        """
        raise NotImplementedError


class CronTriggerExecutor(BaseExecutor):
    """Schedule trigger — just passes through with trigger metadata."""
    node_type = "trigger_cron"

    async def execute(self, node_config, input_data, broadcast=None):
        cron_expr = node_config.get("cron_expression", "0 9 * * *")
        return {
            "trigger": "cron",
            "cron_expression": cron_expr,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Trigger fired (cron: {cron_expr})"
        }


class EventTriggerExecutor(BaseExecutor):
    """Event/manual trigger — passes through trigger context."""
    node_type = "trigger_event"

    async def execute(self, node_config, input_data, broadcast=None):
        return {
            "trigger": "event",
            "event_type": node_config.get("event_type", "manual"),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "message": "Event trigger fired",
            **input_data
        }


class EmailReadExecutor(BaseExecutor):
    """Read emails via IMAP."""
    node_type = "email_read"

    async def execute(self, node_config, input_data, broadcast=None):
        host = node_config.get("imap_host", os.environ.get("IMAP_HOST", "imap.gmail.com"))
        user = node_config.get("email_user", os.environ.get("EMAIL_USER", ""))
        password = node_config.get("email_pass", os.environ.get("EMAIL_PASS", ""))
        folder = node_config.get("folder", "INBOX")
        max_emails = int(node_config.get("max_emails", 5))

        if not user or not password:
            return {
                "success": False,
                "error": "Email credentials not configured. Set EMAIL_USER and EMAIL_PASS in .env",
                "emails": []
            }

        try:
            def _read():
                mail = imaplib.IMAP4_SSL(host)
                mail.login(user, password)
                mail.select(folder)

                _, data = mail.search(None, "ALL")
                email_ids = data[0].split()
                recent_ids = email_ids[-max_emails:] if len(email_ids) > max_emails else email_ids

                emails = []
                for eid in reversed(recent_ids):
                    _, msg_data = mail.fetch(eid, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                    emails.append({
                        "from": msg.get("From", ""),
                        "subject": msg.get("Subject", ""),
                        "date": msg.get("Date", ""),
                        "body": body[:500],  # Truncate for passing through workflow
                    })

                mail.logout()
                return emails

            emails = await asyncio.get_event_loop().run_in_executor(None, _read)
            return {
                "success": True,
                "email_count": len(emails),
                "emails": emails,
                "message": f"Read {len(emails)} emails from {folder}"
            }
        except Exception as e:
            logger.error(f"EmailRead failed: {e}")
            return {"success": False, "error": str(e), "emails": []}


class EmailSendExecutor(BaseExecutor):
    """Send email via SMTP."""
    node_type = "email_send"

    async def execute(self, node_config, input_data, broadcast=None):
        host = node_config.get("smtp_host", os.environ.get("SMTP_HOST", "smtp.gmail.com"))
        port = int(node_config.get("smtp_port", os.environ.get("SMTP_PORT", "587")))
        user = node_config.get("email_user", os.environ.get("EMAIL_USER", ""))
        password = node_config.get("email_pass", os.environ.get("EMAIL_PASS", ""))
        to_email = node_config.get("to", "")
        subject = node_config.get("subject", "Workflow Notification")
        body = node_config.get("body", "")

        # Template: allow {{variable}} references from input_data
        for key, val in input_data.items():
            if isinstance(val, str):
                body = body.replace(f"{{{{{key}}}}}", val)
                subject = subject.replace(f"{{{{{key}}}}}", val)

        if not user or not password:
            return {
                "success": False,
                "error": "Email credentials not configured. Set EMAIL_USER and EMAIL_PASS in .env",
            }
        if not to_email:
            return {"success": False, "error": "No recipient email specified in node config"}

        try:
            def _send():
                msg = MIMEMultipart()
                msg["From"] = user
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body or "Sent by Neural AI Workflow Engine", "plain"))

                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    server.login(user, password)
                    server.send_message(msg)

            await asyncio.get_event_loop().run_in_executor(None, _send)
            return {"success": True, "message": f"Email sent to {to_email}", "to": to_email, "subject": subject}
        except Exception as e:
            logger.error(f"EmailSend failed: {e}")
            return {"success": False, "error": str(e)}


class TaskCreateExecutor(BaseExecutor):
    """Create a task in the local todo.db."""
    node_type = "task_create"

    async def execute(self, node_config, input_data, broadcast=None):
        import sqlite3
        db_path = Path(__file__).parent.parent.parent / "todo.db"
        title = node_config.get("title", input_data.get("message", "Workflow Task"))
        description = node_config.get("description", json.dumps(input_data, default=str)[:200])
        priority = node_config.get("priority", "medium")

        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    completed_at TEXT
                )
            """)
            cursor = conn.execute(
                "INSERT INTO tasks (title, description, priority, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
                (title, description, priority, datetime.now(timezone.utc).isoformat())
            )
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return {"success": True, "task_id": task_id, "title": title, "message": f"Task created: {title}"}
        except Exception as e:
            logger.error(f"TaskCreate failed: {e}")
            return {"success": False, "error": str(e)}


class TaskUpdateExecutor(BaseExecutor):
    """Update a task status in todo.db."""
    node_type = "task_update"

    async def execute(self, node_config, input_data, broadcast=None):
        import sqlite3
        db_path = Path(__file__).parent.parent.parent / "todo.db"
        task_id = node_config.get("task_id", input_data.get("task_id"))
        new_status = node_config.get("status", "completed")

        if not task_id:
            return {"success": False, "error": "No task_id specified"}

        try:
            conn = sqlite3.connect(str(db_path))
            completed_at = datetime.now(timezone.utc).isoformat() if new_status == "completed" else None
            conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                (new_status, completed_at, task_id)
            )
            conn.commit()
            conn.close()
            return {"success": True, "task_id": task_id, "status": new_status, "message": f"Task {task_id} updated to {new_status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class WebSearchExecutor(BaseExecutor):
    """Web search using the existing WebSearchTool."""
    node_type = "web_search"

    async def execute(self, node_config, input_data, broadcast=None):
        query = node_config.get("query", input_data.get("message", input_data.get("query", "")))
        if not query:
            return {"success": False, "error": "No search query specified"}

        try:
            from agent.tools.web_search import WebSearchTool
            tool = WebSearchTool()

            def _search():
                return tool.search(query)

            result = await asyncio.get_event_loop().run_in_executor(None, _search)
            return {
                "success": True,
                "query": query,
                "results": result if isinstance(result, str) else str(result),
                "message": f"Web search completed for: {query}"
            }
        except Exception as e:
            logger.error(f"WebSearch failed: {e}")
            return {"success": False, "error": str(e), "query": query}


class WebScrapeExecutor(BaseExecutor):
    """Scrape a web page using requests + BeautifulSoup."""
    node_type = "web_scrape"

    async def execute(self, node_config, input_data, broadcast=None):
        url = node_config.get("url", input_data.get("url", ""))
        if not url:
            return {"success": False, "error": "No URL specified for scraping"}

        try:
            import requests
            from bs4 import BeautifulSoup

            def _scrape():
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (NeuralAgent Workflow Scraper)"
                })
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Remove script/style
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()

                title = soup.title.string if soup.title else ""
                text = soup.get_text(separator="\n", strip=True)
                return title, text[:3000]  # Truncate to keep manageable

            title, text = await asyncio.get_event_loop().run_in_executor(None, _scrape)
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": text,
                "message": f"Scraped: {title or url}"
            }
        except Exception as e:
            logger.error(f"WebScrape failed: {e}")
            return {"success": False, "error": str(e), "url": url}


class FileReadExecutor(BaseExecutor):
    """Read a file from disk."""
    node_type = "file_read"

    async def execute(self, node_config, input_data, broadcast=None):
        file_path = node_config.get("path", input_data.get("file_path", ""))
        if not file_path:
            return {"success": False, "error": "No file path specified"}

        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}
            if not path.is_file():
                return {"success": False, "error": f"Not a file: {file_path}"}

            content = path.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "file_path": str(path),
                "content": content[:5000],  # Truncate for workflow passing
                "size_bytes": path.stat().st_size,
                "message": f"Read file: {path.name} ({path.stat().st_size} bytes)"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class FileWriteExecutor(BaseExecutor):
    """Write content to a file."""
    node_type = "file_write"

    async def execute(self, node_config, input_data, broadcast=None):
        file_path = node_config.get("path", input_data.get("file_path", ""))
        content = node_config.get("content", "")

        # If no explicit content, serialize input_data as the file content
        if not content:
            content = input_data.get("content", input_data.get("results", json.dumps(input_data, indent=2, default=str)))

        if not file_path:
            # Auto-generate a filename in workspace
            workspace = Path(__file__).parent.parent.parent / "workspace"
            workspace.mkdir(exist_ok=True)
            file_path = str(workspace / f"workflow_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(path),
                "size_bytes": len(content),
                "message": f"Wrote {len(content)} bytes to {path.name}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class NotifyExecutor(BaseExecutor):
    """Send a notification — system tray + optional Telegram."""
    node_type = "notify"

    async def execute(self, node_config, input_data, broadcast=None):
        title = node_config.get("title", "Workflow Alert")
        message = node_config.get("message", input_data.get("message", "Workflow step completed"))
        send_telegram = node_config.get("send_telegram", True)

        results = {"success": True, "notifications_sent": []}

        # System notification
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message[:256],
                timeout=10,
                app_name="Neural AI Agent"
            )
            results["notifications_sent"].append("system")
        except Exception as e:
            logger.warning(f"System notification failed: {e}")

        # Telegram notification
        if send_telegram:
            try:
                telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
                chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
                if telegram_token and chat_id:
                    import requests
                    resp = requests.post(
                        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"🤖 *{title}*\n\n{message}", "parse_mode": "Markdown"},
                        timeout=10
                    )
                    if resp.ok:
                        results["notifications_sent"].append("telegram")
                    else:
                        logger.warning(f"Telegram notification failed: {resp.text}")
            except Exception as e:
                logger.warning(f"Telegram notification failed: {e}")

        results["message"] = f"Notifications sent: {', '.join(results['notifications_sent']) or 'none'}"
        return results


class ConditionExecutor(BaseExecutor):
    """If/Else condition — evaluates an expression and sets a branch flag."""
    node_type = "condition"

    async def execute(self, node_config, input_data, broadcast=None):
        field = node_config.get("field", "success")
        operator = node_config.get("operator", "equals")
        value = node_config.get("value", "true")

        actual = str(input_data.get(field, ""))
        expected = str(value)

        if operator == "equals":
            result = actual.lower() == expected.lower()
        elif operator == "not_equals":
            result = actual.lower() != expected.lower()
        elif operator == "contains":
            result = expected.lower() in actual.lower()
        elif operator == "not_empty":
            result = bool(actual.strip())
        elif operator == "greater_than":
            try:
                result = float(actual) > float(expected)
            except (ValueError, TypeError):
                result = False
        else:
            result = bool(actual)

        return {
            **input_data,
            "condition_result": result,
            "condition_field": field,
            "condition_operator": operator,
            "branch": "true" if result else "false",
            "message": f"Condition '{field} {operator} {value}' → {'TRUE' if result else 'FALSE'}"
        }


class DelayExecutor(BaseExecutor):
    """Wait/Delay — pauses execution for a specified duration."""
    node_type = "delay"

    async def execute(self, node_config, input_data, broadcast=None):
        seconds = int(node_config.get("seconds", 5))
        seconds = min(seconds, 300)  # Cap at 5 minutes
        if broadcast:
            await broadcast("workflow_log", "system", f"Waiting {seconds} seconds...")
        await asyncio.sleep(seconds)
        return {
            **input_data,
            "delay_seconds": seconds,
            "message": f"Waited {seconds} seconds"
        }


class AgentExecutor(BaseExecutor):
    """General AI Agent — routes through NeuralAgent.process_input."""
    node_type = "agent_general"

    async def execute(self, node_config, input_data, broadcast=None):
        prompt = node_config.get("prompt", "")
        if not prompt:
            # Build prompt from input data
            prompt = input_data.get("message", input_data.get("content", json.dumps(input_data, default=str)[:500]))

        # Prepend system instruction if provided
        system_instruction = node_config.get("system_instruction", "")
        if system_instruction:
            prompt = f"{system_instruction}\n\nInput data:\n{prompt}"

        try:
            # Try to use the global agent instance from api_server
            from agent.api_server import agent as global_agent
            if global_agent and hasattr(global_agent, "process_input"):
                response = await global_agent.process_input(prompt)
                return {
                    "success": True,
                    "response": response,
                    "message": f"AI Agent responded ({len(response)} chars)"
                }
            else:
                return {
                    "success": False,
                    "error": "Agent not initialized. Start the Python backend first.",
                    "response": ""
                }
        except Exception as e:
            logger.error(f"AgentExecutor failed: {e}")
            return {"success": False, "error": str(e), "response": ""}


class CoderAgentExecutor(BaseExecutor):
    """Coding Agent — routes through agent with code-focused system prompt."""
    node_type = "agent_coder"

    async def execute(self, node_config, input_data, broadcast=None):
        prompt = node_config.get("prompt", input_data.get("message", ""))
        coding_prompt = f"""You are a coding assistant. Analyze the following and provide clean, working code.

Task: {prompt}

Input data: {json.dumps(input_data, default=str)[:1000]}

Respond with well-structured code and brief explanation."""

        try:
            from agent.api_server import agent as global_agent
            if global_agent and hasattr(global_agent, "process_input"):
                response = await global_agent.process_input(coding_prompt)
                return {"success": True, "response": response, "message": "Coding agent responded"}
            else:
                return {"success": False, "error": "Agent not initialized", "response": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "response": ""}


class TraderAgentExecutor(BaseExecutor):
    """Trading Agent — routes through the trading analysis pipeline."""
    node_type = "agent_trader"

    async def execute(self, node_config, input_data, broadcast=None):
        symbol = node_config.get("symbol", "AAPL")
        action = node_config.get("action", "analyze")
        prompt = f"Analyze {symbol} stock. Action: {action}. Provide market analysis and recommendation."

        try:
            from agent.api_server import agent as global_agent
            if global_agent and hasattr(global_agent, "process_input"):
                response = await global_agent.process_input(prompt)
                return {"success": True, "symbol": symbol, "response": response, "message": f"Trading analysis for {symbol}"}
            else:
                return {"success": False, "error": "Agent not initialized", "response": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "response": ""}


class CalendarEventExecutor(BaseExecutor):
    """Create a calendar event (generates .ics file)."""
    node_type = "calendar_event"

    async def execute(self, node_config, input_data, broadcast=None):
        title = node_config.get("title", input_data.get("title", "Workflow Event"))
        date = node_config.get("date", datetime.now().strftime("%Y-%m-%d"))
        time_str = node_config.get("time", "09:00")
        duration_minutes = int(node_config.get("duration_minutes", 60))
        description = node_config.get("description", input_data.get("message", ""))

        try:
            workspace = Path(__file__).parent.parent.parent / "workspace"
            workspace.mkdir(exist_ok=True)
            ics_path = workspace / f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ics"

            ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Neural AI Agent//Workflow Engine//EN
BEGIN:VEVENT
DTSTART:{date.replace('-', '')}T{time_str.replace(':', '')}00
DURATION:PT{duration_minutes}M
SUMMARY:{title}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""

            ics_path.write_text(ics_content)
            return {
                "success": True,
                "event_title": title,
                "event_file": str(ics_path),
                "message": f"Calendar event created: {title} on {date} at {time_str}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class CalendarCheckExecutor(BaseExecutor):
    """Check for upcoming events (reads .ics files from workspace)."""
    node_type = "calendar_check"

    async def execute(self, node_config, input_data, broadcast=None):
        workspace = Path(__file__).parent.parent.parent / "workspace"
        events = []

        try:
            if workspace.exists():
                for ics_file in workspace.glob("event_*.ics"):
                    content = ics_file.read_text()
                    # Simple parsing
                    summary = ""
                    dtstart = ""
                    for line in content.split("\n"):
                        if line.startswith("SUMMARY:"):
                            summary = line[8:].strip()
                        elif line.startswith("DTSTART:"):
                            dtstart = line[8:].strip()
                    if summary:
                        events.append({"title": summary, "date": dtstart, "file": str(ics_file)})

            return {
                "success": True,
                "events": events,
                "event_count": len(events),
                "message": f"Found {len(events)} upcoming events"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "events": []}


# ── EXECUTOR REGISTRY ──

EXECUTOR_REGISTRY: Dict[str, BaseExecutor] = {
    "trigger_cron": CronTriggerExecutor(),
    "trigger_event": EventTriggerExecutor(),
    "email_read": EmailReadExecutor(),
    "email_send": EmailSendExecutor(),
    "task_create": TaskCreateExecutor(),
    "task_update": TaskUpdateExecutor(),
    "calendar_event": CalendarEventExecutor(),
    "calendar_check": CalendarCheckExecutor(),
    "web_search": WebSearchExecutor(),
    "web_scrape": WebScrapeExecutor(),
    "file_read": FileReadExecutor(),
    "file_write": FileWriteExecutor(),
    "notify": NotifyExecutor(),
    "condition": ConditionExecutor(),
    "delay": DelayExecutor(),
    "agent_general": AgentExecutor(),
    "agent_coder": CoderAgentExecutor(),
    "agent_trader": TraderAgentExecutor(),
}


def get_executor(node_type_id: str) -> Optional[BaseExecutor]:
    """Get the executor for a given node type/tool ID."""
    # Direct match
    if node_type_id in EXECUTOR_REGISTRY:
        return EXECUTOR_REGISTRY[node_type_id]

    # Fuzzy match by prefix
    for key, executor in EXECUTOR_REGISTRY.items():
        if node_type_id.startswith(key):
            return executor

    logger.warning(f"No executor found for node type: {node_type_id}")
    return None
