import asyncio
import logging
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from gitsummarize.exceptions.exceptions import GitHubAccessError
from pydantic import BaseModel

from gitsummarize.auth.auth import verify_token, verify_token_optional
from gitsummarize.auth.key_manager import KeyGroup, KeyManager
from gitsummarize.clients.openai import OpenAIClient
from gitsummarize.clients.supabase import SupabaseClient
from src.gitsummarize.clients.github import GithubClient
from src.gitsummarize.clients.google_genai import GoogleGenAI

load_dotenv()

logger = logging.getLogger(__name__)

gh = GithubClient(os.getenv("GITHUB_TOKEN"))
openai = OpenAIClient(os.getenv("OPENAI_API_KEY"))

# Make SupabaseClient initialization optional - only initialize if SUPABASE_URL is set
supabase = None
if os.getenv("SUPABASE_URL"):
    supabase = SupabaseClient(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ADMIN_KEY"))

key_manager = KeyManager()
for i in range(1, int(os.getenv("NUM_GEMINI_KEYS")) + 1):
    key_manager.add_key(KeyGroup.GEMINI, os.getenv(f"GEMINI_API_KEY_{i}"))


app = FastAPI()


class SummarizeRequest(BaseModel):
    repo_url: str
    gemini_key: Optional[str] = None


@app.post("/summarize", operation_id="summarize_repo")
async def summarize(request: SummarizeRequest, _: str = Depends(verify_token)):
    if not _validate_repo_url(request.repo_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    logger.info(f"Summarizing repository: {request.repo_url}")

    directory_structure = await gh.get_directory_structure_from_url(request.repo_url)
    all_content = await gh.get_all_content_from_url(request.repo_url)

    key_1 = request.gemini_key or key_manager.get_key(KeyGroup.GEMINI)
    key_2 = request.gemini_key or key_manager.get_key(KeyGroup.GEMINI)

    try:
        client_1, client_2 = GoogleGenAI(key_1), GoogleGenAI(key_2)
        business_summary = await client_1.get_business_summary(
            directory_structure, all_content
        )
        technical_documentation = await client_2.get_technical_documentation(
            directory_structure, all_content
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Supabase calls commented out for local usage without Supabase dependency
    # supabase.insert_repo_summary(
    #     request.repo_url, business_summary, technical_documentation
    # )
    # try:
    #     await _update_repo_metadata(request.repo_url)
    # except GitHubAccessError as e:
    #     logger.error(f"Error updating repo metadata for {request.repo_url}: {e}")
    return JSONResponse(content={"message": "Repository summarized successfully"})


@app.post("/repo-metadata-cron")
async def repo_metadata_cron(_: str = Depends(verify_token)):
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    repo_urls = supabase.get_all_repo_urls()
    for repo_url in repo_urls:
        try:
            metadata = await gh.get_repo_metadata_from_url(repo_url)
            supabase.upsert_repo_metadata(repo_url, metadata)
        except GitHubAccessError as e:
            logger.error(f"Error updating repo metadata for {repo_url}: {e}")


@app.post("/summarize-local", operation_id="summarize_store_local")
async def summarize_store_local(
    request: SummarizeRequest, _: Optional[str] = Depends(verify_token_optional)
):
    if not _validate_repo_url(request.repo_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    logger.info(f"Summarizing repository: {request.repo_url}")

    directory_structure = await gh.get_directory_structure_from_url(request.repo_url)
    all_content = await gh.get_all_content_from_url(request.repo_url)

    business_summary, technical_documentation = await asyncio.gather(
        openai.get_business_summary(directory_structure, all_content),
        openai.get_technical_documentation(directory_structure, all_content),
    )

    # Create output directory if it doesn't exist
    os.makedirs("tmp/openai", exist_ok=True)
    
    with open("tmp/openai/business_summary.txt", "w") as f:
        f.write(business_summary)
    with open("tmp/openai/technical_documentation.txt", "w") as f:
        f.write(technical_documentation)
    
    return JSONResponse(content={"message": "Repository summarized successfully"})


def _validate_repo_url(repo_url: str) -> bool:
    return repo_url.startswith("https://github.com/")


async def _update_repo_metadata(repo_url: str):
    try:
        metadata = await gh.get_repo_metadata_from_url(repo_url)
        # Only update Supabase if it's initialized
        if supabase:
            supabase.upsert_repo_metadata(repo_url, metadata)
    except GitHubAccessError as e:
        logger.error(f"Error updating repo metadata for {repo_url}: {e}")
