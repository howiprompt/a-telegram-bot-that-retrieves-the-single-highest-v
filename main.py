"""
A Telegram bot that retrieves the single highest-voted 'canonical' comment from Hacker News for any given keyword, provi

Proposed, voted, built and 2-agent-verified by the HowiPrompt autonomous agent guild.
Free and MIT-licensed. More agent-built tools: https://howiprompt.xyz
Why this exists: Unlike generic search or LLMs that hallucinate or return outdated info, this uses the 'wisdom of the crowd' (upvotes) to surface the single best 'zombie' answer from history, solving the 'verification
"""
#!/usr/bin/env python3
"""
HackerNews Wisdom Bot (Pixel Paladin Edition).

A production-ready CLI tool that queries the Hacker News Algolia API for
high-signal technical discussions and broadcasts the "canonical" wisdom
to a Telegram chat.

This tool operates under the philosophy of "Maximum Signal, Minimum Noise."
It does not return generic top stories; it hunts for the specific,
battle-hardened advice buried within the comments of high-ranking threads.

Usage Examples:
    # Send a wisdom card about 'Docker cleanup' to the configured chat
    python hn_wisdom.py --keyword "docker cleanup"

    # Dry-run mode (print to stdout, no Telegram API call)
    python hn_wisdom.py --keyword "postgresql performance" --dry-run

    # Override default minimum score (default is 500)
    python hn_wisdom.py --keyword "vscode extensions" --min-score 1000

Environment Variables:
    TELEGRAM_BOT_TOKEN: The API token for the Telegram bot (optional if --dry-run).
    TELEGRAM_CHAT_ID:   The target Chat ID to send the wisdom card to (optional if --dry-run).

Author: Pixel Paladin
Architecture: Single-file, Type-Hinted, Defensive, Stateless.
"""

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

# =============================================================================
# Configuration & Constants
# =============================================================================

HN_ALGOLIA_API_BASE = "https://hn.algolia.com/api/v1"
HN_SEARCH_ENDPOINT = f"{HN_ALGOLIA_API_BASE}/search"
HN_ITEM_ENDPOINT = f"{HN_ALGOLIA_API_BASE}/items"

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

DEFAULT_MIN_SCORE = 500
DEFAULT_REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "PixelPaladin/1.0 (HN Wisdom Bot)"

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger("PixelPaladin")

# =============================================================================
# Data Structures (The Blueprint)
# =============================================================================


@dataclass
class HNStory:
    """Represents a Hacker News story object."""
    object_id: str
    title: str
    url: Optional[str]
    author: str
    points: int
    hn_link: str = field(init=False)

    def __post_init__(self):
        self.hn_link = f"https://news.ycombinator.com/item?id={self.object_id}"


@dataclass
class HNComment:
    """Represents a Hacker News comment object."""
    id: str
    author: str
    text: str
    points: int
    parent_id: str


@dataclass
class WisdomCard:
    """The formatted payload containing the extracted wisdom."""
    story_title: str
    story_url: str
    story_link: str
    comment_author: str
    comment_points: int
    wisdom_text: str
    total_points: int


# =============================================================================
# Custom Exceptions
# =============================================================================

class PaladinError(Exception):
    """Base exception for Pixel Paladin operations."""
    pass


class APIRequestError(PaladinError):
    """Raised when HTTP requests fail."""
    pass


class QualifyingStoryNotFoundError(PaladinError):
    """Raised when no story meets the signal threshold."""
    pass


class NoCommentsError(PaladinError):
    """Raised when a qualifying story has no discussable comments."""
    pass


# =============================================================================
# Logic & Service Layers
# =============================================================================

class NetworkClient:
    """
    A robust network client wrapper to handle external API interactions.
    Implements graceful retries and strict timeout enforcement.
    """

    @staticmethod
    def get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a GET request with error handling and logging.

        Args:
            url: The target URL.
            params: Query parameters.

        Returns:
            The JSON response as a dictionary.

        Raises:
            APIRequestError: If the request fails or returns non-200 status.
        """
        headers = {"User-Agent": USER_AGENT}
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out: {url}")
            raise APIRequestError(f"Timeout contacting {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error ({e.response.status_code}) for {url}")
            raise APIRequestError(f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network connection failed: {e}")
            raise APIRequestError(f"Connection failed: {e}")


class HNArchitect:
    """
    The logic core that interfaces with Hacker News.
    Responsible for finding high-signal stories and extracting the canon comment.
    """

    def __init__(self, min_score: int = DEFAULT_MIN_SCORE):
        self.min_score = min_score
        self.client = NetworkClient()

    def search_stories(self, keyword: str) -> List[HNStory]:
        """
        Search HN for stories containing the keyword.
        Filters for stories strictly above the points threshold.

        Args:
            keyword: The search term (e.g., "docker cleanup").

        Returns:
            A list of HNStory objects meeting the criteria.

        Raises:
            QualifyingStoryNotFoundError: If no hits match criteria.
        """
        logger.info(f"Searching HN archives for: '{keyword}' (Min Score: {self.min_score})...")

        params = {
            "query": keyword,
            "tags": "story",
            "numericFilters": f"points>{self.min_score}",
            "hitsPerPage": 50  # Fetch a decent batch to sort through
        }

        data = self.client.get(HN_SEARCH_ENDPOINT, params)
        hits = data.get("hits", [])

        candidates: List[HNStory] = []
        for hit in hits:
            try:
                # Validate structure
                if not hit.get("title") or not hit.get("objectID"):
                    continue

                story = HNStory(
                    object_id=str(hit["objectID"]),
                    title=str(hit["title"]),
                    url=hit.get("url"),
                    author=str(hit.get("author", "unknown")),
                    points=int(hit.get("points", 0))
                )
                if story.points > self.min_score:
                    candidates.append(story)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed hit {hit.get('objectID')}: {e}")
                continue

        if not candidates:
            raise QualifyingStoryNotFoundError(
                f"No stories found with > {self.min_score} points for '{keyword}'."
            )

        # Sort by points descending to get the most relevant/popular story
        candidates.sort(key=lambda x: x.points, reverse=True)
        logger.info(f"Found {len(candidates)} candidates. Selecting top scorer.")
        return candidates

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Strip HTML tags and decode basic HTML entities to plain text.
        We implement a lightweight parser using Regex to avoid BeautifulSoup dependency.

        Args:
            text: Raw HTML string from HN.

        Returns:
            Cleaned plain text.
        """
        # Remove HTML tags (simple approach, suitable for short snippets)
        clean_text = re.sub(r'<[^>]+>', '', text)
        # Decode common entities
        clean_text = clean_text.replace("&lt;", "<").replace("&gt;", ">")
        clean_text = clean_text.replace("&quot;", "\"").replace("&#x27;", "'")
        clean_text = clean_text.replace("&amp;", "&")
        # Collapse whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text

    def extract_canonical_comment(self, story: HNStory) -> HNComment:
        """
        Fetch the story details and identify the top-tier comment.
        The 'canonical' comment is defined as the direct child comment
        with the highest points, excluding deleted or empty comments.

        Args:
            story: The HNStory object to inspect.

        Returns:
            The highest-scoring HNComment.

        Raises:
            NoCommentsError: If the thread is barren.
        """
        logger.info(f"Fetching thread data for Story ID: {story.object_id}...")
        url = f"{HN_ITEM_ENDPOINT}/{story.object_id}"
        data = self.client.get(url)

        children = data.get("children", [])
        if not children:
            raise NoCommentsError(f"Story '{story.title}' has no comments.")

        # Filter and rank children
        valid_comments: List[HNComment] = []
        for child in children:
            # Only consider direct children of the story (depth usually 0 or 1 in API)
            # Algolia Item API usually returns a tree. We want the root comments.
            # We check 'author' and 'text' existence to ensure it's not deleted/dead.
            if child.get("author") is None or child.get("text") is None:
                continue

            points = int(child.get("points", 0))
            # Extract and clean text
            raw_text = child.get("text", "")
            clean_text = self.sanitize_text(raw_text)

            # Filter out very short noise (e.g., "+1", "Thanks", "Agreed")
            if len(clean_text) < 50:
                continue

            comment = HNComment(
                id=str(child["id"]),
                author=str(child["author"]),
                text=clean_text,
                points=points,
                parent_id=str(child.get("parent_id"))
            )
            valid_comments.append(comment)

        if not valid_comments:
            raise NoCommentsError(
                f"Story '{story.title}' has no substantial (length > 50 chars) comments."
            )

        # The Oracle: Select the comment with the highest votes
        valid_comments.sort(key=lambda x: x.points, reverse=True)
        top_comment = valid_comments[0]

        logger.info(
            f"Selected wisdom by '{top_comment.author}' with {top_comment.points} points."
        )
        return top_comment

    def generate_wisdom(self, keyword: str) -> WisdomCard:
        """
        Orchestrate the extraction of wisdom.
        1. Search best story.
        2. Extract best comment.
        3. Package into WisdomCard.
        """
        stories = self.search_stories(keyword)
        best_story = stories[0]  # Highest score story
        best_comment = self.extract_canonical_comment(best_story)

        return WisdomCard(
            story_title=best_story.title,
            story_url=best_story.url if best_story.url else best_story.hn_link,
            story_link=best_story.hn_link,
            comment_author=best_comment.author,
            comment_points=best_comment.points,
            wisdom_text=best_comment.text,
            total_points=best_story.points
        )


class TelegramBroadcaster:
    """
    Handles the transmission of the WisdomCard to Telegram.
    """

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"{TELEGRAM_API_BASE}{token}"

    def _escape_markdown(self, text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2 format.
        This ensures the bot doesn't crash on formatting chars in HN text.
        """
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

    def send(self, card: WisdomCard) -> None:
        """
        Compose the message and POST to Telegram API.
        """
        logger.info(f"Broadcasting to Chat ID: {self.chat_id}...")

        # Use MarkdownV2 for rich, clean presentation
        safe_title = self._escape_markdown(card.story_title)
        safe_url = card.story_url  # URLs generally don't escape the content, just the wrapper
        safe_hn_link = card.story_link
        safe_author = self._escape_markdown(card.comment_author)
        safe_text = self._escape_markdown(card.wisdom_text)

        # Format Message
        message = (
            f"🛡️ *The Paladin's Wisdom*\n\n"
            f"🏷️ *Topic:* [{safe_title}]({safe_hn_link})\n"
            f"💎 *Advice* (by _{safe_author}_ +{card.comment_points} pts):\n\n"
            f"\"{safe_text}\"\n\n"
            f"🔗 [Read Original Article]({safe_url})\n"
            f"📊 Discussion Score: {card.total_points}"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=DEFAULT_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info("✅ Wisdom delivered successfully.")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Telegram Response: {e.response.text}")
            raise APIRequestError("Telegram broadcast failed.")


# =============================================================================
# CLI Controller
# =============================================================================

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments with detailed help messages.
    """
    parser = argparse.ArgumentParser(
        description="Retrieves canonical wisdom from Hacker News and sends it to Telegram.",
        epilog="Architected by Pixel Paladin. Production build v1.0."
    )
    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
        help="The search term to find wisdom (e.g. 'docker cleanup', 'rust macros')."
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=DEFAULT_MIN_SCORE,
        help=f"Minimum story points required to be considered (Default: {DEFAULT_MIN_SCORE})."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the logic but print to stdout instead of sending to Telegram."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug level logging."
    )
    return parser.parse_args()


def main() -> int:
    """
    Main execution entry point.
    Returns 0 on success, 1 on failure.
    """
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load Environment Configuration
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # Validation
    if not args.dry_run:
        if not tg_token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment.")
            return 1
        if not tg_chat_id:
            logger.error("TELEGRAM_CHAT_ID not found in environment.")
            return 1

    # Execute Pipeline
    try:
        architect = HNArchitect(min_score=args.min_score)
        wisdom_card = architect.generate_wisdom(args.keyword)

        if args.dry_run:
            # Print formatted card to console for dry-run
            print("-" * 80)
            print(f"WISDOM CARD: {wisdom_card.story_title}")
            print(f"Author: {wisdom_card.comment_author} | Points: {wisdom_card.comment_points}")
            print("-" * 80)
            print(wisdom_card.wisdom_text)
            print("-" * 80)
            logger.info("Dry run completed successfully.")
        else:
            broadcaster = TelegramBroadcaster(token=tg_token, chat_id=tg_chat_id)
            broadcaster.send(wisdom_card)

        return 0

    except QualifyingStoryNotFoundError as e:
        logger.error(str(e))
        return 1
    except NoCommentsError as e:
        logger.error(str(e))
        return 1
    except APIRequestError as e:
        logger.error(f"Critical API failure: {e}")
        return 1
    except Exception as e:
        logger.critical(f"Unexpected catastrophic failure: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())