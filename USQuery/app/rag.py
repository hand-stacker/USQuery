import asyncio
from typing import List, Optional
from django.conf import settings
from asgiref.sync import sync_to_async
from google import genai
from bs4 import BeautifulSoup
import aiohttp

from app.utils import connectASYNC

CHUNK_SIZE = 2000       # ~500 tokens
CHUNK_OVERLAP_PARAS = 1 # paragraphs to carry into next chunk for overlap
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768
TOP_K = 5


def _split_into_chunks(text: str) -> List[str]:
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > CHUNK_SIZE and current:
            chunks.append('\n'.join(current))
            overlap = current[-CHUNK_OVERLAP_PARAS:]
            current = overlap + [para]
            current_len = sum(len(p) for p in current)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append('\n'.join(current))

    return [c for c in chunks if len(c.strip()) > 100]


async def _embed_text(client, text: str) -> List[float]:
    result = await asyncio.to_thread(
        lambda: client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
    )
    return result.embeddings[0].values


async def _fetch_bill_full_text(bill) -> Optional[str]:
    apiURL = settings.CONGRESS_DIR + "bill/" + bill.getURL()
    header_str = "?api_key=" + settings.CONGRESS_KEY + "&format=json&limit=250"

    async with aiohttp.ClientSession() as session:
        versions_data = await connectASYNC(session, apiURL + "/text", header_str)
        if not versions_data or not versions_data.get("textVersions"):
            return None

        latest_dt = None
        latest_url = None
        from datetime import datetime
        for version in versions_data["textVersions"]:
            date_str = version.get("date")
            if not date_str or not version.get("formats"):
                continue
            try:
                dt = datetime.fromisoformat(date_str[:19])
            except ValueError:
                continue
            if latest_dt is None or dt > latest_dt:
                latest_dt = dt
                latest_url = version["formats"][0]["url"]

        if not latest_url:
            return None

        html = await connectASYNC(session, latest_url, "", False)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator='\n')


async def index_bill(bill) -> bool:
    """Chunk and embed a bill's full text, storing results in BillChunk. Returns True on success."""
    from app.models import BillChunk

    if not settings.GEMINI_KEY:
        return False

    try:
        text = await _fetch_bill_full_text(bill)
    except Exception as e:
        print(f"RAG: failed to fetch bill text for {bill.id}: {e}")
        return False

    if not text:
        return False

    chunks = _split_into_chunks(text)
    if not chunks:
        return False

    client = genai.Client(api_key=settings.GEMINI_KEY)

    # Embed concurrently, max 3 in-flight at a time to stay within rate limits
    sem = asyncio.Semaphore(3)

    async def embed_with_limit(chunk: str) -> List[float]:
        async with sem:
            return await _embed_text(client, chunk)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(embed_with_limit(chunk)) for chunk in chunks]

    embeddings = [t.result() for t in tasks]

    bill_chunks = [
        BillChunk(bill_id=bill.id, chunk_index=i, content=chunks[i], embedding=embeddings[i])
        for i in range(len(chunks))
    ]

    await BillChunk.objects.filter(bill_id=bill.id).adelete()
    await BillChunk.objects.abulk_create(bill_chunks)
    return True


async def retrieve_relevant_chunks(bill_id: int, query: str, top_k: int = TOP_K) -> List[str]:
    """Embed the query and return the top_k most relevant bill text chunks."""
    from app.models import BillChunk
    from pgvector.django import CosineDistance

    if not settings.GEMINI_KEY:
        return []

    try:
        client = genai.Client(api_key=settings.GEMINI_KEY)
        query_embedding = await _embed_text(client, query)
    except Exception as e:
        print(f"RAG: failed to embed query: {e}")
        return []

    try:
        qs = (
            BillChunk.objects
            .filter(bill_id=bill_id)
            .order_by(CosineDistance('embedding', query_embedding))[:top_k]
        )
        chunks = await sync_to_async(list)(qs)
        return [c.content for c in chunks]
    except Exception as e:
        print(f"RAG: retrieval failed for bill {bill_id}: {e}")
        return []
