import os
import time
import atexit
import pickle
import logging
import urllib.parse
import requests

logger = logging.getLogger(__name__)


class PageCache:
    """Cache pages and pageviews so walks never refetch.

    Pageviews persist to disk; pages stay in memory only.
    """

    PAGEVIEWS_URL = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia/all-access/user/{title}/daily/{start}/{end}"
    )

    def __init__(self, wiki, user_agent, min_interval=0.1, max_retries=5,
                 timeout=30, cache_path="pageviews_cache.pkl", flush_every=25):
        self.wiki = wiki
        self.user_agent = user_agent
        self.pages = {}
        self.categories = {}
        self._last_call = 0.0
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self.page_fetches = 0
        self.pageview_fetches = 0
        self._cache_path = cache_path
        self._flush_every = flush_every
        self._unsaved = 0
        self.pageviews = self._load_cache()
        atexit.register(self.save)

    def _load_cache(self):
        if self._cache_path and os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, "rb") as f:
                    data = pickle.load(f)
                logger.info("loaded %d cached pageviews from %s",
                            len(data), self._cache_path)
                return data
            except Exception as e:
                logger.warning("could not load cache %s: %s", self._cache_path, e)
        return {}

    def save(self):
        """Atomically write the pageviews cache to disk."""
        if not self._cache_path:
            return
        tmp = self._cache_path + ".tmp"
        try:
            with open(tmp, "wb") as f:
                pickle.dump(self.pageviews, f)
            os.replace(tmp, self._cache_path)
            self._unsaved = 0
        except Exception as e:
            logger.warning("could not save cache %s: %s", self._cache_path, e)

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def get_page(self, title):
        if title not in self.pages:
            self._throttle()
            self.page_fetches += 1
            logger.debug("fetch page: %s", title)
            self.pages[title] = self.wiki.page(title)
        return self.pages[title]

    def get_categories(self, page):
        """Return the set of category titles for a page."""
        if page.title not in self.categories:
            self._throttle()
            self.page_fetches += 1
            logger.debug("fetch categories: %s", page.title)
            self.categories[page.title] = set(page.categories.keys())
        return self.categories[page.title]

    def get_pageviews(self, title, start="20240101", end="20241231"):
        """Sum of daily pageviews over [start, end] (YYYYMMDD), 0 if unavailable."""
        key = (title, start, end)
        if key not in self.pageviews:
            url = self.PAGEVIEWS_URL.format(
                title=urllib.parse.quote(title.replace(" ", "_"), safe=""),
                start=start,
                end=end,
            )
            self.pageviews[key] = self._get_views(url, title)
            self._unsaved += 1
            if self._unsaved >= self._flush_every:
                self.save()
        return self.pageviews[key]

    def _get_views(self, url, title):
        """GET a pageviews URL, retrying on 429, 5xx and network errors.

        Never raises; returns 0 on failure.
        """
        for attempt in range(self._max_retries):
            self._throttle()
            self.pageview_fetches += 1
            logger.debug("fetch pageviews: %s", title)
            try:
                resp = self._session.get(url, timeout=self._timeout)
            except requests.exceptions.RequestException as e:
                wait = 2 ** attempt
                logger.warning("network error on %r: %s; retry in %.0fs (%d/%d)",
                               title, e, wait, attempt + 1, self._max_retries)
                time.sleep(wait)
                continue

            if resp.status_code == 404:
                return 0
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                logger.warning("HTTP %d on %r; backing off %.1fs (%d/%d)",
                               resp.status_code, title, wait,
                               attempt + 1, self._max_retries)
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                logger.warning("HTTP %d on %r; treating as 0 views",
                               resp.status_code, title)
                return 0

            try:
                items = resp.json().get("items", [])
            except ValueError:
                logger.warning("bad JSON for %r; treating as 0 views", title)
                return 0
            return sum(item["views"] for item in items)

        logger.warning("giving up on %r after %d retries; using 0 views",
                       title, self._max_retries)
        return 0
