#!/usr/bin/env python3
"""
Standalone CLI script for summarizing GitHub repositories locally without Supabase.

Usage:
    python backend/summarize_local.py https://github.com/example-owner/example-repo

Requirements:
    - Set GITHUB_TOKEN and GEMINI_API_KEY in the script or as environment variables
    - Install dependencies: poetry install (from backend directory)
    
Output:
    Saves summaries to tmp/summaries/{repo_owner}_{repo_name}/
    - business_summary.txt
    - technical_documentation.txt
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src directory to path so we can import gitsummarize modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gitsummarize.clients.github import GithubClient
from gitsummarize.clients.google_genai import GoogleGenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

# API Keys - Replace with your actual keys or set as environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "your_github_token_here")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_1", os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here"))


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Parse a GitHub URL to extract owner and repo name.
    
    Args:
        url: GitHub repository URL (e.g., https://github.com/owner/repo)
        
    Returns:
        Tuple of (owner, repo_name)
    """
    if not url.startswith("https://github.com/"):
        raise ValueError("Invalid GitHub URL. Must start with https://github.com/")
    
    # Remove protocol and split
    url = url.replace("https://", "").replace("http://", "")
    parts = url.split("/")
    
    if len(parts) < 3:
        raise ValueError("Invalid GitHub URL format")
    
    owner = parts[1]
    repo = parts[2].rstrip('/')
    
    return owner, repo


async def summarize_repository(repo_url: str) -> None:
    """
    Summarize a GitHub repository and save results to local files.
    
    Args:
        repo_url: Full GitHub repository URL
    """
    logger.info(f"Starting summarization for: {repo_url}")
    
    # Validate API keys
    if GITHUB_TOKEN == "your_github_token_here":
        logger.warning("⚠️  GITHUB_TOKEN not set. Using placeholder. Please set your actual GitHub token.")
    if GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("⚠️  GEMINI_API_KEY not set. Using placeholder. Please set your actual Gemini API key.")
    
    # Initialize clients
    gh_client = GithubClient(GITHUB_TOKEN)
    gemini_client = GoogleGenAI(GEMINI_API_KEY)
    
    # Parse URL to get owner and repo
    owner, repo = parse_github_url(repo_url)
    logger.info(f"Repository: {owner}/{repo}")
    
    # Fetch repository structure and content
    logger.info("Fetching directory structure...")
    directory_structure = await gh_client.get_directory_structure_from_url(repo_url)
    
    logger.info("Fetching repository content...")
    all_content = await gh_client.get_all_content_from_url(repo_url)
    
    logger.info("Generating summaries with Google Gemini (this may take a while)...")
    
    # Generate summaries in parallel using two separate clients
    gemini_client_2 = GoogleGenAI(GEMINI_API_KEY)
    business_summary, technical_documentation = await asyncio.gather(
        gemini_client.get_business_summary(directory_structure, all_content),
        gemini_client_2.get_technical_documentation(directory_structure, all_content),
    )
    
    # Create output directory
    output_dir = Path(f"tmp/summaries/{owner}_{repo}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save summaries to files
    business_summary_path = output_dir / "business_summary.txt"
    technical_documentation_path = output_dir / "technical_documentation.txt"
    
    logger.info(f"Saving business summary to: {business_summary_path}")
    with open(business_summary_path, "w", encoding="utf-8") as f:
        f.write(business_summary)
    
    logger.info(f"Saving technical documentation to: {technical_documentation_path}")
    with open(technical_documentation_path, "w", encoding="utf-8") as f:
        f.write(technical_documentation)
    
    logger.info("✅ Summarization complete!")
    logger.info(f"📁 Output directory: {output_dir.absolute()}")


def main():
    """Main entry point for the CLI script."""
    if len(sys.argv) != 2:
        print("Usage: python backend/summarize_local.py https://github.com/owner/repo")
        print("\nExample:")
        print("  python backend/summarize_local.py https://github.com/example-owner/example-repo")
        sys.exit(1)
    
    repo_url = sys.argv[1]
    
    try:
        # Run the async summarization function
        asyncio.run(summarize_repository(repo_url))
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
