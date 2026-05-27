import aiohttp
import logging
import re
from config.settings import TMDB_API_KEY

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r'[:\-_\'´`’ʻ"“”·.\[\]()]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _score_titles(query: str, item: dict) -> float:
    """Score how well a TMDB result item matches the search query.
    Returns 0.0-1.0 based on word overlap across all title fields.
    """
    q = _normalize(query)
    q_words = q.split()
    if not q_words:
        return 0.0

    candidates = [item.get("title"), item.get("name"),
                  item.get("original_title"), item.get("original_name")]
    # Also try the original title in a different script (enrich search)
    best = 0.0
    for cand in candidates:
        if not cand:
            continue
        t = _normalize(cand)
        t_words = t.split()
        if not t_words:
            continue

        # Exact match after normalization = perfect
        if q == t:
            return 1.0

        t_set = set(t_words)
        q_set = set(q_words)

        intersection = q_set & t_set
        if not intersection:
            continue

        query_coverage = len(intersection) / len(q_set)
        title_coverage = len(intersection) / len(t_set)
        score = (query_coverage + title_coverage) / 2

        # Bonus if query is a substring of title or vice versa
        if q in t or t in q:
            score += 0.2

        # Bonus if the candidate is longer (more complete title)
        if len(t_words) >= len(q_words):
            score += 0.1

        best = max(best, min(score, 1.0))

    return best


class MetadataAPI:
    """Fetch metadata from TMDB."""

    def __init__(self):
        self.tmdb_key = TMDB_API_KEY
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

    async def get_tv_details(self, tmdb_id: int) -> dict | None:
        """Get season/episode counts for a TV show from TMDB."""
        try:
            session = await self._get_session()
            url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
            params = {"api_key": self.tmdb_key, "language": "en-US"}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
            seasons = {}
            for s in data.get("seasons") or []:
                sn = s.get("season_number")
                ec = s.get("episode_count", 0)
                if sn is not None and sn > 0:
                    seasons[sn] = ec
            return {
                "seasons": seasons,
                "total_episodes": data.get("number_of_episodes", 0),
                "total_seasons": data.get("number_of_seasons", 0),
            }
        except Exception as e:
            logger.error(f"TMDB tv details error: {e}")
            return None

    async def _fetch_and_details(self, title: str) -> dict | None:
        """Search + optionally fetch tv season details in one async call."""
        result = await self._search_tmdb(title)
        if result and result.get('type') in ('tv', 'anime') and result.get('tmdb_id'):
            details = await self.get_tv_details(result['tmdb_id'])
            if details:
                result['tv_details'] = details
        return result

    async def search(self, title: str, year: int | None = None) -> dict | None:
        """Search TMDB for movie or TV show. Returns best-matching result."""
        if not title:
            return None

        cache_key = (title.lower().strip(), year)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.tmdb_key:
            result = await self._search_tmdb(title, year)
            if result:
                self._cache[cache_key] = result
                return result

        self._cache[cache_key] = None
        return None

    async def _search_tmdb(self, title: str, year: int | None = None) -> dict | None:
        """Search TMDB with query fallback: try full query, then progressively shorter."""
        words = title.split()
        # Try progressively shorter queries when full query returns nothing
        for i in range(len(words), 0, -1):
            sub = ' '.join(words[:i])
            result = await self._search_tmdb_single(sub, year)
            if result:
                return result
        return None

    async def _search_tmdb_single(self, title: str, year: int | None = None) -> dict | None:
        """Single TMDB search, score all results by title match, return best."""
        try:
            session = await self._get_session()
            params_base = {"api_key": self.tmdb_key, "query": title, "language": "en-US"}
            if year:
                params_movie = {**params_base, "year": str(year)}
                params_tv = {**params_base, "first_air_date_year": str(year)}
            else:
                params_movie = params_tv = params_base

            movie_url = "https://api.themoviedb.org/3/search/movie"
            tv_url = "https://api.themoviedb.org/3/search/tv"

            async with session.get(movie_url, params=params_movie) as resp:
                movie_data = await resp.json() if resp.status == 200 else {"results": []}
            async with session.get(tv_url, params=params_tv) as resp:
                tv_data = await resp.json() if resp.status == 200 else {"results": []}

            # Score ALL results from both categories
            scored: list[tuple[float, float, dict, str]] = []

            for item in movie_data.get("results", []):
                s = _score_titles(title, item)
                pop = item.get("popularity", 0)
                scored.append((s, pop, item, "movie"))

            for item in tv_data.get("results", []):
                s = _score_titles(title, item)
                pop = item.get("popularity", 0)
                scored.append((s, pop, item, "tv"))

            if not scored:
                return None

            # Sort by score desc, then popularity desc
            scored.sort(key=lambda x: (-x[0], -x[1]))
            best_score, best_pop, best_item, category = scored[0]

            # If best score is 0 (no word overlap — cross-language query),
            # fall back to popularity-based selection
            if best_score < 0.01:
                scored.sort(key=lambda x: (-x[1], -x[0]))
                best_score, best_pop, best_item, category = scored[0]

            genre_ids = best_item.get("genre_ids", [])
            if category == "movie":
                orig_lang = best_item.get("original_language", "")
                is_animated = 16 in genre_ids
                mtype = "anime" if is_animated and orig_lang == "ja" else ("cartoon" if is_animated else "movie")
                return {
                    "type": mtype,
                    "title": best_item.get("title"),
                    "year": int(best_item["release_date"][:4]) if best_item.get("release_date") else None,
                    "tmdb_id": best_item.get("id"),
                    "genre_ids": genre_ids,
                    "original_language": orig_lang,
                    "confidence": round(0.5 + best_score * 0.5, 2),
                }
            else:
                origin_country = best_item.get("origin_country", [])
                is_anime = 16 in genre_ids and "JP" in origin_country
                return {
                    "type": "anime" if is_anime else "tv",
                    "title": best_item.get("name"),
                    "year": int(best_item["first_air_date"][:4]) if best_item.get("first_air_date") else None,
                    "tmdb_id": best_item.get("id"),
                    "genre_ids": genre_ids,
                    "origin_country": origin_country,
                    "confidence": round(0.5 + best_score * 0.5, 2),
                }

        except Exception as e:
            logger.error(f"TMDB error: {e}")

        return None
