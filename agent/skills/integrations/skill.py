"""
Integrations Skill - API-based app control.

Provides high-precision, stateless API integrations for:
- Spotify (playback, playlists)
- Discord (messages, channels)
- Notion (pages, databases)
- GitHub (issues, PRs)

These are faster and more reliable than UI automation.
"""

import logging
from typing import Dict, Any, Optional, List

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class IntegrationsSkill(BaseSkill):
    """
    API-based integrations for common apps.
    
    Actions:
    - spotify_play: Play music
    - spotify_pause: Pause playback
    - spotify_search: Search for music
    - spotify_queue: Add to queue
    - spotify_current: Get current track
    - discord_send: Send message to channel
    - discord_read: Read channel messages
    - notion_create: Create a page
    - notion_query: Query a database
    - github_create_issue: Create GitHub issue
    - github_list_prs: List PRs
    """
    
    def __init__(self):
        super().__init__()
        self._spotify = None
        self._discord = None
        self._notion = None
        self._github = None
        self._available_integrations = []
    
    @property
    def name(self) -> str:
        return "integrations"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="integrations",
            version="1.0.0",
            description="API-based app control (Spotify, Discord, Notion, GitHub)",
            actions=[
                # Spotify
                "spotify_play", "spotify_pause", "spotify_search", 
                "spotify_queue", "spotify_current", "spotify_next", "spotify_prev",
                # Discord
                "discord_send", "discord_read",
                # Notion
                "notion_create", "notion_query",
                # GitHub
                "github_create_issue", "github_list_prs", "github_list_issues"
            ],
            requires=["spotipy", "discord.py", "notion-client", "PyGithub"],
            permissions=["network", "api_tokens"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize available API clients."""
        # Spotify
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            import os
            
            client_id = os.environ.get("SPOTIFY_CLIENT_ID")
            client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
            redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
            
            if client_id and client_secret:
                self._spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing"
                ))
                self._available_integrations.append("spotify")
                self.logger.info("Spotify API initialized")
        except Exception as e:
            self.logger.warning(f"Spotify not available: {e}")
        
        # GitHub
        try:
            from github import Github
            import os
            
            github_token = os.environ.get("GITHUB_TOKEN")
            if github_token:
                self._github = Github(github_token)
                self._available_integrations.append("github")
                self.logger.info("GitHub API initialized")
        except Exception as e:
            self.logger.warning(f"GitHub not available: {e}")
        
        # Notion
        try:
            from notion_client import Client
            import os
            
            notion_token = os.environ.get("NOTION_TOKEN")
            if notion_token:
                self._notion = Client(auth=notion_token)
                self._available_integrations.append("notion")
                self.logger.info("Notion API initialized")
        except Exception as e:
            self.logger.warning(f"Notion not available: {e}")
        
        super().on_load()
        self.logger.info(f"Integrations skill loaded: {self._available_integrations}")
    
    def on_unload(self) -> None:
        """Cleanup."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # Spotify patterns
        if "spotify" in self._available_integrations:
            if any(x in intent_lower for x in ["play on spotify", "spotify play", "queue", "what's playing", "current song"]):
                return 0.9
        
        # GitHub patterns
        if "github" in self._available_integrations:
            if any(x in intent_lower for x in ["create issue", "github", "pull request", "pr", "repo"]):
                return 0.85
        
        # Notion patterns
        if "notion" in self._available_integrations:
            if any(x in intent_lower for x in ["notion", "create page", "add to notion"]):
                return 0.85
        
        # Discord patterns
        if "discord" in self._available_integrations:
            if any(x in intent_lower for x in ["discord", "send message", "read channel"]):
                return 0.85
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute an integration action."""
        
        handlers = {
            # Spotify
            "spotify_play": self._spotify_play,
            "spotify_pause": self._spotify_pause,
            "spotify_search": self._spotify_search,
            "spotify_queue": self._spotify_queue,
            "spotify_current": self._spotify_current,
            "spotify_next": self._spotify_next,
            "spotify_prev": self._spotify_prev,
            # GitHub
            "github_create_issue": self._github_create_issue,
            "github_list_prs": self._github_list_prs,
            "github_list_issues": self._github_list_issues,
            # Notion
            "notion_create": self._notion_create,
            "notion_query": self._notion_query,
            # Discord
            "discord_send": self._discord_send,
            "discord_read": self._discord_read,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Integration action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== SPOTIFY ====================
    
    def _spotify_play(self, params: Dict, context: Dict) -> SkillResult:
        """Play music on Spotify."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        uri = params.get("uri")
        query = params.get("query")
        
        try:
            if query:
                # Search and play
                results = self._spotify.search(q=query, type="track", limit=1)
                if results["tracks"]["items"]:
                    track = results["tracks"]["items"][0]
                    uri = track["uri"]
                    track_name = track["name"]
                    artist = track["artists"][0]["name"]
                else:
                    return SkillResult(success=False, error=f"No results for: {query}")
            
            if uri:
                self._spotify.start_playback(uris=[uri])
                return SkillResult(
                    success=True,
                    message=f"Now playing: {track_name} by {artist}" if query else "Started playback"
                )
            else:
                self._spotify.start_playback()
                return SkillResult(success=True, message="Resumed playback")
                
        except Exception as e:
            return SkillResult(success=False, error=f"Spotify play failed: {e}")
    
    def _spotify_pause(self, params: Dict, context: Dict) -> SkillResult:
        """Pause Spotify playback."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        try:
            self._spotify.pause_playback()
            return SkillResult(success=True, message="Playback paused")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _spotify_search(self, params: Dict, context: Dict) -> SkillResult:
        """Search Spotify."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        query = params.get("query", "")
        search_type = params.get("type", "track")
        
        try:
            results = self._spotify.search(q=query, type=search_type, limit=5)
            
            items = results.get(f"{search_type}s", {}).get("items", [])
            formatted = []
            for item in items:
                if search_type == "track":
                    formatted.append(f"{item['name']} by {item['artists'][0]['name']}")
                else:
                    formatted.append(item['name'])
            
            return SkillResult(
                success=True,
                data={"results": items, "formatted": formatted},
                message=f"Found {len(items)} results"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _spotify_queue(self, params: Dict, context: Dict) -> SkillResult:
        """Add to Spotify queue."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        uri = params.get("uri")
        query = params.get("query")
        
        try:
            if query:
                results = self._spotify.search(q=query, type="track", limit=1)
                if results["tracks"]["items"]:
                    uri = results["tracks"]["items"][0]["uri"]
            
            if not uri:
                return SkillResult(success=False, error="Track URI or query required")
            
            self._spotify.add_to_queue(uri)
            return SkillResult(success=True, message="Added to queue")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _spotify_current(self, params: Dict, context: Dict) -> SkillResult:
        """Get current playing track."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        try:
            current = self._spotify.current_playback()
            if current and current.get("item"):
                track = current["item"]
                return SkillResult(
                    success=True,
                    data={
                        "track": track["name"],
                        "artist": track["artists"][0]["name"],
                        "album": track["album"]["name"],
                        "is_playing": current["is_playing"]
                    },
                    message=f"Now playing: {track['name']} by {track['artists'][0]['name']}"
                )
            return SkillResult(success=True, message="Nothing currently playing")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _spotify_next(self, params: Dict, context: Dict) -> SkillResult:
        """Skip to next track."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        try:
            self._spotify.next_track()
            return SkillResult(success=True, message="Skipped to next track")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _spotify_prev(self, params: Dict, context: Dict) -> SkillResult:
        """Previous track."""
        if not self._spotify:
            return SkillResult(success=False, error="Spotify not configured")
        
        try:
            self._spotify.previous_track()
            return SkillResult(success=True, message="Previous track")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    # ==================== GITHUB ====================
    
    def _github_create_issue(self, params: Dict, context: Dict) -> SkillResult:
        """Create a GitHub issue."""
        if not self._github:
            return SkillResult(success=False, error="GitHub not configured")
        
        repo_name = params.get("repo")
        title = params.get("title")
        body = params.get("body", "")
        
        if not repo_name or not title:
            return SkillResult(success=False, error="Repo and title required")
        
        try:
            repo = self._github.get_repo(repo_name)
            issue = repo.create_issue(title=title, body=body)
            return SkillResult(
                success=True,
                data={"issue_number": issue.number, "url": issue.html_url},
                message=f"Created issue #{issue.number}: {title}"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _github_list_prs(self, params: Dict, context: Dict) -> SkillResult:
        """List PRs for a repo."""
        if not self._github:
            return SkillResult(success=False, error="GitHub not configured")
        
        repo_name = params.get("repo")
        state = params.get("state", "open")
        
        if not repo_name:
            return SkillResult(success=False, error="Repo name required")
        
        try:
            repo = self._github.get_repo(repo_name)
            prs = list(repo.get_pulls(state=state)[:10])
            
            pr_list = [{"number": pr.number, "title": pr.title, "author": pr.user.login} for pr in prs]
            
            return SkillResult(
                success=True,
                data={"prs": pr_list},
                message=f"Found {len(pr_list)} {state} PRs"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _github_list_issues(self, params: Dict, context: Dict) -> SkillResult:
        """List issues for a repo."""
        if not self._github:
            return SkillResult(success=False, error="GitHub not configured")
        
        repo_name = params.get("repo")
        state = params.get("state", "open")
        
        if not repo_name:
            return SkillResult(success=False, error="Repo name required")
        
        try:
            repo = self._github.get_repo(repo_name)
            issues = list(repo.get_issues(state=state)[:10])
            
            issue_list = [{"number": i.number, "title": i.title} for i in issues if not i.pull_request]
            
            return SkillResult(
                success=True,
                data={"issues": issue_list},
                message=f"Found {len(issue_list)} {state} issues"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    # ==================== NOTION ====================
    
    def _notion_create(self, params: Dict, context: Dict) -> SkillResult:
        """Create a Notion page."""
        if not self._notion:
            return SkillResult(success=False, error="Notion not configured")
        
        parent_id = params.get("parent_id")
        title = params.get("title")
        content = params.get("content", "")
        
        if not parent_id or not title:
            return SkillResult(success=False, error="Parent ID and title required")
        
        try:
            page = self._notion.pages.create(
                parent={"page_id": parent_id},
                properties={"title": {"title": [{"text": {"content": title}}]}},
                children=[{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"text": [{"type": "text", "text": {"content": content}}]}
                }] if content else []
            )
            return SkillResult(
                success=True,
                data={"page_id": page["id"]},
                message=f"Created page: {title}"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _notion_query(self, params: Dict, context: Dict) -> SkillResult:
        """Query a Notion database."""
        if not self._notion:
            return SkillResult(success=False, error="Notion not configured")
        
        database_id = params.get("database_id")
        
        if not database_id:
            return SkillResult(success=False, error="Database ID required")
        
        try:
            results = self._notion.databases.query(database_id=database_id)
            
            pages = []
            for page in results.get("results", [])[:10]:
                props = page.get("properties", {})
                title_prop = next((v for v in props.values() if v.get("type") == "title"), None)
                title = ""
                if title_prop and title_prop.get("title"):
                    title = title_prop["title"][0]["plain_text"] if title_prop["title"] else ""
                pages.append({"id": page["id"], "title": title})
            
            return SkillResult(
                success=True,
                data={"pages": pages},
                message=f"Found {len(pages)} items"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    # ==================== DISCORD ====================
    
    def _discord_send(self, params: Dict, context: Dict) -> SkillResult:
        """Send Discord message (requires webhook)."""
        webhook_url = params.get("webhook_url")
        message = params.get("message")
        
        if not webhook_url or not message:
            return SkillResult(success=False, error="Webhook URL and message required")
        
        try:
            import requests
            response = requests.post(webhook_url, json={"content": message})
            response.raise_for_status()
            return SkillResult(success=True, message="Message sent")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _discord_read(self, params: Dict, context: Dict) -> SkillResult:
        """Read Discord messages (not implemented - requires bot)."""
        return SkillResult(
            success=False, 
            error="Discord read requires a bot. Use webhook for sending."
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check integrations skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._available_integrations:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview integration action."""
        previews = {
            "spotify_play": f"Would play: {params.get('query') or params.get('uri', 'resume')}",
            "github_create_issue": f"Would create issue: {params.get('title', 'unknown')} in {params.get('repo', 'unknown')}",
            "notion_create": f"Would create page: {params.get('title', 'unknown')}",
            "discord_send": f"Would send message via webhook",
        }
        
        return previews.get(action, f"Would execute integrations.{action}")
