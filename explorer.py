import time
import math
import random
import logging
from collections import Counter
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

logger = logging.getLogger(__name__)


def _short(label, n=33):
    return label if len(label) <= n else label[: n - 1] + "…"

# These walkers choose from the current page alone, not from walk history,
# so their decision can be memoized per page.
DETERMINISTIC_WALKERS = {"greedy", "contrarian"}

# Namespace 0 is the article space; Category:, Template: and the rest are excluded.
MAIN_NAMESPACE = 0


class Explorer:
    def __init__(self, walker_name, walker_fn, cache, max_candidates=50):
        self.walker_name = walker_name
        self.walker_fn = walker_fn
        self.cache = cache
        self.max_candidates = max_candidates
        self.deterministic = walker_name in DETERMINISTIC_WALKERS
        self.decisions = {}

    def _step(self, current):
        """Return the next page, or None if current has no outgoing links."""
        if self.deterministic and current.title in self.decisions:
            return self.cache.get_page(self.decisions[current.title])

        candidates = [
            p for p in current.links.values()
            if p.namespace == MAIN_NAMESPACE and p.title != current.title
        ]
        if not candidates:
            return None

        # Hub pages are subsampled to max_candidates to bound lookups per step.
        if len(candidates) > self.max_candidates:
            candidates = random.sample(candidates, self.max_candidates)

        next_page = self.walker_fn(current, candidates, self.cache)

        if self.deterministic:
            self.decisions[current.title] = next_page.title

        return next_page

    def walk(self, start_title, length):
        current = self.cache.get_page(start_title)
        path = [current.title]
        for step in range(length):
            next_page = self._step(current)
            if next_page is None:
                logger.debug("  step %d: dead end at %r", step, current.title)
                break
            if next_page.title == current.title:
                logger.debug("  step %d: stuck at %r", step, current.title)
                break
            logger.debug("  step %d: %r -> %r", step, current.title, next_page.title)
            current = next_page
            path.append(current.title)
        return path

    def run_experiment(self, start_titles, length):
        paths = []
        for i, start in enumerate(start_titles, 1):
            t0 = time.monotonic()
            try:
                path = self.walk(start, length)
            except Exception:
                # A failed walk is skipped so it doesn't abort the whole experiment.
                logger.exception("[%s] walk %d from %r failed; skipping",
                                 self.walker_name, i, start)
                path = [start]
            logger.info(
                "[%s] walk %d/%d from %r: %d pages in %.1fs "
                "(page fetches=%d, pageview fetches=%d)",
                self.walker_name, i, len(start_titles), start, len(path),
                time.monotonic() - t0,
                self.cache.page_fetches, self.cache.pageview_fetches,
            )
            paths.append(path)
        counter = Counter(title for path in paths for title in path)
        return paths, counter


def visit_entropy(counter):
    """Shannon entropy, in bits, of the visit distribution."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log2(c / total) for c in counter.values()
    )


def coverage(counter):
    return len(counter)


def weighted_mean_popularity(counter, cache):
    """Mean pageviews of visited pages, weighted by visit count."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return sum(cache.get_pageviews(p) * c for p, c in counter.items()) / total


def detect_cycle(path):
    """Titles between a page's first and second occurrence, or None if none repeats."""
    seen = {}
    for i, title in enumerate(path):
        if title in seen:
            return path[seen[title]:i]
        seen[title] = i
    return None


def plot_top_pages(counter, top_n=10, title="Most visited pages", ax=None):
    """Horizontal bar chart of the most visited pages, into ax if one is given."""
    own_fig = ax is None
    if own_fig:
        _, ax = plt.subplots(figsize=(8, 5))

    top = counter.most_common(top_n)
    if not top:
        ax.set_title(title + " (no pages)")
        ax.axis("off")
        return

    labels, counts = zip(*top)
    labels = [_short(l) for l in labels]
    ax.barh(labels[::-1], counts[::-1])
    ax.set_xlabel("Visits")
    ax.set_title(title)
    ax.tick_params(labelsize=7)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    if own_fig:
        plt.tight_layout()
        plt.show()
