"""Fetch metadata from AniList GraphQL API."""
import aiohttp
import logging
import re

logger = logging.getLogger(__name__)


def _normalize(title: str) -> str:
    """Normalize title for comparison."""
    t = title.lower().strip()
    t = re.sub(r'[:\-_\'´`’ʻ"“”·.\[\]()]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _score_titles(query: str, item: dict) -> float:
    """Score how well an AniList result matches the query (0.0-1.0)."""
    q = _normalize(query)
    q_words = q.split()
    if not q_words:
        return 0.0

    title_data = item.get("title", {})
    candidates = [title_data.get("romaji"), title_data.get("english"),
                  title_data.get("native")]
    best = 0.0
    for cand in candidates:
        if not cand:
            continue
        t = _normalize(cand)
        t_words = t.split()
        if not t_words:
            continue
        if q == t:
            return 1.0
        intersection = set(q_words) & set(t_words)
        if not intersection:
            continue
        query_cov = len(intersection) / len(q_words)
        title_cov = len(intersection) / len(t_words)
        score = (query_cov + title_cov) / 2
        if q in t or t in q:
            score += 0.2
        if len(t_words) >= len(q_words):
            score += 0.1
        best = max(best, min(score, 1.0))
    return best


class AniListAPI:
    """Fetch metadata from AniList GraphQL API."""

    ENDPOINT = "https://graphql.anilist.co"

    SEARCH_QUERY = """
    query ($search: String, $page: Int) {
      Page(page: $page, perPage: 5) {
        media(search: $search, type: ANIME) {
          id
          title {
            romaji
            english
            native
          }
          format
          seasonYear
          genres
          countryOfOrigin
        }
      }
    }
    """

    def __init__(self):
        self._session = None
        self._cache = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def search(self, title: str) -> dict | None:
        """Search AniList for an anime by title.
        Returns best-matching result using title scoring.
        """
        if not title:
            return None

        cache_key = title.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self._graphql_search(title)
        self._cache[cache_key] = result
        return result

    async def _graphql_search(self, title: str) -> dict | None:
        """Execute GraphQL search on AniList. Uses title scoring with query fallback."""
        words = title.split()
        for i in range(len(words), 0, -1):
            sub = ' '.join(words[:i])
            result = await self._graphql_search_single(sub)
            if result:
                return result
        return None

    async def _graphql_search_single(self, title: str) -> dict | None:
        """Single GraphQL search on AniList."""
        try:
            session = await self._get_session()
            variables = {"search": title, "page": 1}
            payload = {"query": self.SEARCH_QUERY, "variables": variables}
            async with session.post(self.ENDPOINT, json=payload) as resp:
                if resp.status != 200:
                    logger.debug(f"AniList status={resp.status}")
                    return None
                data = await resp.json()

            results = data.get("data", {}).get("Page", {}).get("media", [])
            if not results:
                return None

            # Score all results, keep best above threshold
            scored: list[tuple[float, dict]] = []
            for item in results:
                s = _score_titles(title, item)
                scored.append((s, item))

            scored.sort(key=lambda x: -x[0])
            best_score, best_item = scored[0]

            if best_score < 0.1:
                return None

            fmt = best_item.get("format", "")
            if fmt not in ("TV", "TV_SHORT", "OVA", "ONA", "SPECIAL", "MOVIE"):
                return None

            title_data = best_item.get("title", {})
            best_title = (
                title_data.get("english")
                or title_data.get("romaji")
                or title_data.get("native")
            )
            return {
                "type": "anime",
                "title": best_title,
                "year": best_item.get("seasonYear"),
                "anilist_id": best_item.get("id"),
                "confidence": round(0.4 + best_score * 0.5, 2),
            }

        except Exception as e:
            logger.error(f"AniList error: {e}")

        return None
