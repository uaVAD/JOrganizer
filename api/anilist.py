"""Fetch metadata from AniList GraphQL API."""
import aiohttp
import logging
import re

logger = logging.getLogger(__name__)


def _normalize(title: str) -> str:
    """Normalize title for exact comparison."""
    t = title.lower().strip()
    t = re.sub(r'[:\-_\'´`’ʻ"“”·.\[\]()]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


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
        Only returns result if the returned title matches the query exactly.
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
        """Execute GraphQL search on AniList. Only exact title matches are trusted."""
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

            norm_query = _normalize(title)

            for item in results:
                title_data = item.get("title", {})
                candidates = [
                    title_data.get("romaji"),
                    title_data.get("english"),
                    title_data.get("native"),
                ]
                for cand in candidates:
                    if cand and _normalize(cand) == norm_query:
                        fmt = item.get("format", "")
                        best_title = (
                            title_data.get("english")
                            or title_data.get("romaji")
                            or title_data.get("native")
                        )
                        if fmt in ("TV", "TV_SHORT", "OVA", "ONA", "SPECIAL", "MOVIE"):
                            return {
                                "type": "anime",
                                "title": best_title,
                                "year": item.get("seasonYear"),
                                "anilist_id": item.get("id"),
                                "confidence": 0.8,
                            }

        except Exception as e:
            logger.error(f"AniList error: {e}")

        return None
