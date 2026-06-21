import random


def drunk(current, candidates, cache):
    return random.choice(candidates) if candidates else current


def greedy(current, candidates, cache):
    top = current
    best = -1
    for page in candidates:
        views = cache.get_pageviews(page.title)
        if views > best:
            top = page
            best = views
    return top


def contrarian(current, candidates, cache):
    least = current
    best = float("inf")
    for page in candidates:
        views = cache.get_pageviews(page.title)
        if views < best:
            least = page
            best = views
    return least


def homebody(current, candidates, cache):
    top = current
    categories = cache.get_categories(current)
    best = 0
    for page in candidates:
        shared = len(categories & cache.get_categories(page))
        if shared > best:
            top = page
            best = shared
    return top
