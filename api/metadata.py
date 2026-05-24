import aiohttp
import logging
from config.settings import TMDB_API_KEY

logger = logging.getLogger(__name__)


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
        """Search TMDB for movie or TV show."""
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
        """Search TMDB for movie or TV show using shared session."""
        try:
            session = await self._get_session()
            movie_params = {"api_key": self.tmdb_key, "query": title, "language": "en-US"}
            tv_params = {"api_key": self.tmdb_key, "query": title, "language": "en-US"}
            if year:
                movie_params["year"] = str(year)
                tv_params["first_air_date_year"] = str(year)

            movie_url = "https://api.themoviedb.org/3/search/movie"
            tv_url = "https://api.themoviedb.org/3/search/tv"

            async with session.get(movie_url, params=movie_params) as resp:
                movie_data = await resp.json() if resp.status == 200 else {"results": []}
            async with session.get(tv_url, params=tv_params) as resp:
                tv_data = await resp.json() if resp.status == 200 else {"results": []}

            movie_results = movie_data.get("results", [])
            tv_results = tv_data.get("results", [])

            movie_pop = movie_results[0].get("popularity", 0) if movie_results else 0
            tv_pop = tv_results[0].get("popularity", 0) if tv_results else 0

            if movie_pop >= tv_pop and movie_results:
                item = movie_results[0]
                genre_ids = item.get("genre_ids", [])
                orig_lang = item.get("original_language", "")
                is_animated = 16 in genre_ids
                if is_animated:
                    mtype = "anime" if orig_lang == "ja" else "cartoon"
                else:
                    mtype = "movie"
                return {
                    "type": mtype,
                    "title": item.get("title"),
                    "year": int(item["release_date"][:4]) if item.get("release_date") else None,
                    "tmdb_id": item.get("id"),
                    "genre_ids": genre_ids,
                    "original_language": orig_lang,
                    "confidence": 0.9,
                }
            elif tv_results:
                item = tv_results[0]
                genre_ids = item.get("genre_ids", [])
                origin_country = item.get("origin_country", [])
                is_anime = 16 in genre_ids and "JP" in origin_country
                return {
                    "type": "anime" if is_anime else "tv",
                    "title": item.get("name"),
                    "year": int(item["first_air_date"][:4]) if item.get("first_air_date") else None,
                    "tmdb_id": item.get("id"),
                    "genre_ids": genre_ids,
                    "origin_country": origin_country,
                    "confidence": 0.9,
                }

        except Exception as e:
            logger.error(f"TMDB error: {e}")

        return None
