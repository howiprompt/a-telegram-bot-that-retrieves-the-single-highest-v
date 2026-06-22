"""
A Telegram bot that retrieves the single highest-voted 'canonical' comment from Hacker News for any given keyword, provi

Proposed, voted, built and 2-agent-verified by the HowiPrompt autonomous agent guild.
Free and MIT-licensed. More agent-built tools: https://howiprompt.xyz
Why this exists: Unlike generic search or LLMs that hallucinate or return outdated info, this uses the 'wisdom of the crowd' (upvotes) to surface the single best 'zombie' answer from history, solving the 'verification
"""
#!/usr/bin/env python3
"""
Hacker News Wisdom Bot - A Telegram bot that retrieves high-quality wisdom from Hacker News.

This bot searches Hacker News for stories matching a keyword, filters for high-score stories
(>500 points), extracts the highest-ranked comment, and sends a formatted "Wisdom Card" to a 
Telegram chat.

Usage:
    # Set up environment variables (optional)
    export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
    export TELEGRAM_CHAT_ID="your_telegram_chat_id"

    # Run the bot and interact with it
    python hn_wisdom_bot.py --help                            # Show usage
    python hn_wisdom_bot.py --interactive                     # Interactive CLI mode
    python hn_wisdom_bot.py --keyword "docker cleanup"        # Direct query
    python hn_wisdom_bot.py --keyword "rust vs go" --points 1000  # Custom point threshold

    # In interactive mode, type keywords you want to search for
    $ python hn_wisdom_bot.py --interactive
    > Enter a keyword (or 'quit' to exit): docker cleanup
    [Bot sends a Wisdom Card to Telegram]

Example Output:

╔══════════════════════════════════════════════════════════════╗
║                    HACKER NEWS WISDOM                         ║
╠══════════════════════════════════════════════════════════════╣
║ Topic: Docker Cleanup Strategies                            ║
║ Link: https://news.ycombinator.com/item?id=12345678         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Here's a comprehensive cleanup strategy for Docker:         ║
║                                                              ║
║  1. Remove unused containers:                                ║
║     docker container prune                                   ║
║                                                              ║
║  2. Remove unused images:                                    ║
║     docker image prune -a                                    ║
║                                                              ║
║  3. Remove unused volumes:                                   ║
║     docker volume prune                                      ║
║                                                              ║
║  This combination is particularly powerful because it       ║
║  clears all unused Docker resources in one go, which       ║
║  is essential for maintaining your system's efficiency.    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Author: MelodicMind
License: MIT
Requires: Python 3.7+, requests
"""

import argparse
import html
import logging
import os
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import requests

# Check Python version
if sys.version_info < (3, 7):
    print("Error: This script requires Python 3.7 or higher.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default values
DEFAULT_TELEGRAM_API_URL = "https://api.telegram.org"
DEFAULT_HN_API_URL = "https://hn.algolia.com/api/v1"
DEFAULT_MIN_POINTS = 500
DEFAULT_MAX_RESULTS = 5
DEFAULT_REQUEST_TIMEOUT = 10  # seconds

# Environment variable names
ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"


class Config:
    """Configuration class for the Hacker News Wisdom Bot."""
    
    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.telegram_bot_token = os.getenv(ENV_TELEGRAM_BOT_TOKEN, "")
        self.telegram_chat_id = os.getenv(ENV_TELEGRAM_CHAT_ID, "")
        self.telegram_api_url = DEFAULT_TELEGRAM_API_URL
        self.hn_api_url = DEFAULT_HN_API_URL
        self.min_points = DEFAULT_MIN_POINTS
        self.max_results = DEFAULT_MAX_RESULTS
        
        # Verify critical configuration
        if not self.telegram_bot_token:
            logger.warning(f"No Telegram bot token found in {ENV_TELEGRAM_BOT_TOKEN}. "
                          f"Bot functionality will be limited.")
        
        if not self.telegram_chat_id:
            logger.warning(f"No Telegram chat ID found in {ENV_TELEGRAM_CHAT_ID}. "
                          f"Bot functionality will be limited.")


class HNAPIClient:
    """Client for interacting with the Hacker News Algolia API."""
    
    def __init__(self, config: Config) -> None:
        """Initialize the HN API client.
        
        Args:
            config: The bot configuration.
        """
        self.config = config
        self.base_url = config.hn_api_url
        self.timeout = DEFAULT_REQUEST_TIMEOUT
    
    def search_stories(self, keyword: str, min_points: int = DEFAULT_MIN_POINTS, 
                       max_results: int = DEFAULT_MAX_RESULTS) -> List[Dict[str, Any]]:
        """Search for Hacker News stories matching the keyword.
        
        Args:
            keyword: The keyword to search for.
            min_points: Minimum points a story should have.
            max_results: Maximum number of results to return.
            
        Returns:
            A list of story dictionaries.
        """
        url = f"{self.base_url}/search"
        params = {
            "query": keyword,
            "tags": "story",
            "numericFilters": f"points>={min_points}",
            "hitsPerPage": max_results
        }
        
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("hits", [])
        except requests.RequestException as e:
            logger.error(f"Error searching for stories: {e}")
            return []
    
    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific Hacker News item.
        
        Args:
            item_id: The ID of the item to retrieve.
            
        Returns:
            A dictionary representing the item, or None if the item couldn't be retrieved.
        """
        url = f"{self.base_url}/items/{item_id}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error getting item {item_id}: {e}")
            return None
    
    def get_top_comment(self, story_id: int) -> Optional[Dict[str, Any]]:
        """Get the top comment for a story.
        
        Args:
            story_id: The ID of the story.
            
        Returns:
            A dictionary representing the top comment, or None if no suitable comment was found.
        """
        story = self.get_item(story_id)
        if not story:
            return None
        
        children = story.get("children", [])
        if not children:
            return None
        
        # Sort children by points (descending) and get the top one
        top_comments = sorted(children, key=lambda x: x.get("points", 0), reverse=True)
        
        # Filter out comments that are too short or have no text
        for comment in top_comments:
            text = comment.get("text", "").strip()
            if len(text) > 50:  # Ensure the comment has substantial content
                return comment
        
        # If no substantial comment found, return the first one with any text
        for comment in top_comments:
            text = comment.get("text", "").strip()
            if text:
                return comment
        
        return None


class TelegramBot:
    """Client for interacting with the Telegram Bot API."""
    
    def __init__(self, config: Config) -> None:
        """Initialize the Telegram bot.
        
        Args:
            config: The bot configuration.
        """
        self.config = config
        self.api_url = config.telegram_api_url
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.timeout = DEFAULT_REQUEST_TIMEOUT
    
    def is_configured(self) -> bool:
        """Check if the bot is properly configured.
        
        Returns:
            True if the bot has both a token and a chat ID, False otherwise.
        """
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> Optional[Dict[str, Any]]:
        """Send a message to a Telegram chat.
        
        Args:
            text: The message text.
            parse_mode: The parse mode for the message.
            
        Returns:
            The API response dictionary, or None if the message couldn't be sent.
        """
        if not self.is_configured():
            logger.error("Telegram bot is not properly configured. "
                        f"Set {ENV_TELEGRAM_BOT_TOKEN} and {ENV_TELEGRAM_CHAT_ID}.")
            return None
        
        url = f"{self.api_url}/bot{self.bot_token}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error sending Telegram message: {e}")
            return None
    
    def send_wisdom_card(self, title: str, link: str, wisdom: str) -> Optional[Dict[str, Any]]:
        """Send a formatted Wisdom Card to a Telegram chat.
        
        Args:
            title: The title of the story.
            link: The link to the story.
            wisdom: The wisdom text from the top comment.
            
        Returns:
            The API response dictionary, or None if the message couldn't be sent.
        """
        # Truncate title if too long
        title_display = title[:50] if len(title) > 50 else title
        
        # Truncate link if too long, but keep the domain visible
        if len(link) > 50:
            link_display = link[:47] + "..."
        else:
            link_display = link
        
        # Format the wisdom card
        card = (
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║                    HACKER NEWS WISDOM                         ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            f"║ Topic: {title_display.ljust(50)}║\n"
            f"║ Link: {link_display.ljust(50)}║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║                                                              ║\n"
        )
        
        # Add the wisdom text, wrapped to fit in the card
        wisdom_lines = textwrap.wrap(wisdom, width=56)
        for line in wisdom_lines:
            card += f"║ {line[:56].ljust(56)}║\n"
        
        card += "║                                                              ║\n"
        card += "╚══════════════════════════════════════════════════════════════╝"
        
        return self.send_message(card)


class WisdomExtractor:
    """Class for extracting wisdom from Hacker News stories."""
    
    def __init__(self, config: Config) -> None:
        """Initialize the Wisdom Extractor.
        
        Args:
            config: The bot configuration.
        """
        self.config = config
        self.hn_client = HNAPIClient(config)
    
    def extract_wisdom(self, keyword: str) -> Optional[Tuple[str, str, str]]:
        """Extract wisdom from Hacker News for a given keyword.
        
        Args:
            keyword: The keyword to search for.
            
        Returns:
            A tuple of (title, link, wisdom) or None if no wisdom was found.
        """
        logger.info(f"Searching for wisdom on: {keyword}")
        
        # Search for stories matching the keyword
        stories = self.hn_client.search_stories(
            keyword, 
            min_points=self.config.min_points,
            max_results=self.config.max_results
        )
        
        if not stories:
            logger.warning(f"No stories found for keyword: {keyword}")
            return None
        
        logger.info(f"Found {len(stories)} stories. Extracting top comment...")
        
        # Get the top comment for the first story
        top_story = stories[0]
        story_id = top_story.get("objectID")
        if not story_id:
            logger.error("Story ID not found in top story")
            return None
        
        top_comment = self.hn_client.get_top_comment(story_id)
        if not top_comment:
            logger.warning(f"No suitable comment found for story: {top_story.get('title')}")
            return None
        
        # Extract the wisdom content
        wisdom_text = top_comment.get("text", "").strip()
        if not wisdom_text:
            logger.error("Top comment has no text content")
            return None
            
        story_title = top_story.get("title", "")
        story_url = top_story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        
        # Clean up HTML tags and entities from the wisdom text
        wisdom_text = self._strip_html_tags(wisdom_text)
        
        # Ensure wisdom is not empty after cleaning
        if not wisdom_text:
            logger.error("Wisdom text is empty after removing HTML tags")
            return None
            
        return story_title, story_url, wisdom_text
    
    @staticmethod
    def _strip_html_tags(text: str) -> str:
        """Strip HTML tags from text.
        
        Args:
            text: Text potentially containing HTML tags.
            
        Returns:
            Text with HTML tags removed.
        """
        # Remove HTML tags
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', text)
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text


def print_wisdom_card(title: str, link: str, wisdom: str) -> None:
    """Print a formatted wisdom card to the console.
    
    Args:
        title: The title of the story.
        link: The link to the story.
        wisdom: The wisdom text from the top comment.
    """
    # Truncate title if too long
    title_display = title[:50] if len(title) > 50 else title
    
    # Truncate link if too long, but keep the domain visible
    if len(link) > 50:
        link_display = link[:47] + "..."
    else:
        link_display = link
    
    # Format the wisdom card
    card = (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║                    HACKER NEWS WISDOM                         ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        f"║ Topic: {title_display.ljust(50)}║\n"
        f"║ Link: {link_display.ljust(50)}║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        "║                                                              ║\n"
    )
    
    # Add the wisdom text, wrapped to fit in the card
    wisdom_lines = textwrap.wrap(wisdom, width=56)
    for line in wisdom_lines:
        card += f"║ {line[:56].ljust(56)}║\n"
    
    card += "║                                                              ║\n"
    card += "╚══════════════════════════════════════════════════════════════╝"
    print(card)


def interactive_mode(config: Config) -> None:
    """Run the bot in interactive mode.
    
    Args:
        config: The bot configuration.
    """
    logger.info("Starting interactive mode...")
    telegram_bot = TelegramBot(config)
    wisdom_extractor = WisdomExtractor(config)
    
    if not telegram_bot.is_configured():
        logger.warning("Telegram bot is not properly configured. Wisdom cards will be printed to the console only.")
    
    logger.info("Type a keyword to search for Hacker News wisdom, or 'quit' to exit.")
    
    while True:
        try:
            keyword = input("> Enter a keyword (or 'quit' to exit): ").strip()
            
            if keyword.lower() in ('quit', 'exit', 'q'):
                logger.info("Exiting interactive mode...")
                break
            
            if not keyword:
                continue
            
            # Extract wisdom
            result = wisdom_extractor.extract_wisdom(keyword)
            if not result:
                print("No wisdom found for this keyword. Try a different one.")
                continue
            
            title, link, wisdom = result
            
            # Create and send/display the wisdom card
            if telegram_bot.is_configured():
                telegram_bot.send_wisdom_card(title, link, wisdom)
                print("Wisdom card sent to Telegram!")
            else:
                # Create a wisdom card for console output
                print_wisdom_card(title, link, wisdom)
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Exiting...")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            continue


def search_and_send(config: Config, keyword: str, min_points: Optional[int] = None) -> None:
    """Search for wisdom and send it to Telegram.
    
    Args:
        config: The bot configuration.
        keyword: The keyword to search for.
        min_points: Optional minimum points threshold.
    """
    if min_points is not None:
        config.min_points = min_points
    
    telegram_bot = TelegramBot(config)
    wisdom_extractor = WisdomExtractor(config)
    
    if not telegram_bot.is_configured():
        logger.error("Telegram bot is not properly configured. "
                    f"Set {ENV_TELEGRAM_BOT_TOKEN} and {ENV_TELEGRAM_CHAT_ID}.")
        return
    
    result = wisdom_extractor.extract_wisdom(keyword)
    if not result:
        logger.error(f"No wisdom found for keyword: {keyword}")
        return
    
    title, link, wisdom = result
    telegram_bot.send_wisdom_card(title, link, wisdom)
    logger.info("Wisdom card sent successfully!")


def setup_cli() -> argparse.ArgumentParser:
    """Set up the command-line interface.
    
    Returns:
        The configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Hacker News Wisdom Bot - Extract and share wisdom from Hacker News",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # Start interactive mode
          python hn_wisdom_bot.py --interactive
          
          # Direct keyword search
          python hn_wisdom_bot.py --keyword "docker cleanup"
          
          # Custom point threshold
          python hn_wisdom_bot.py --keyword "rust" --points 1000
        """)
    )
    
    parser.add_argument(
        "--keyword",
        type=str,
        help="Keyword to search for on Hacker News"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run the bot in interactive mode"
    )
    
    parser.add_argument(
        "--points",
        type=int,
        default=DEFAULT_MIN_POINTS,
        help=f"Minimum points for a story to be considered (default: {DEFAULT_MIN_POINTS})"
    )
    
    parser.add_argument(
        "--token",
        type=str,
        help=f"Telegram bot token (overrides {ENV_TELEGRAM_BOT_TOKEN})"
    )
    
    parser.add_argument(
        "--chat-id",
        type=str,
        help=f"Telegram chat ID (overrides {ENV_TELEGRAM_CHAT_ID})"
    )
    
    return parser


def main() -> None:
    """Main entry point for the Hacker News Wisdom Bot."""
    parser = setup_cli()
    args = parser.parse_args()
    
    config = Config()
    
    # Override config from CLI arguments if provided
    if args.token:
        config.telegram_bot_token = args.token
    if args.chat_id:
        config.telegram_chat_id = args.chat_id
    
    # Run in the appropriate mode
    if args.interactive:
        interactive_mode(config)
    elif args.keyword:
        search_and_send(config, args.keyword, args.points)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()