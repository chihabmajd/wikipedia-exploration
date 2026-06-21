# wikipedia-exploration

How does the strategy you use to follow links change where you end up on Wikipedia?

Four link-following rules are run from the same random start pages, at four walk lengths,
and compared on how widely they roam, how concentrated their visits are, how popular the
pages they settle on are, and whether they get stuck in loops.

## The walkers

At each step a walker sees up to 20 outgoing links from the current article and picks one.
Only namespace 0 is followed, so categories, templates and portals are excluded.

| Walker | Rule |
|---|---|
| `drunk` | Uniformly at random |
| `greedy` | The candidate with the most pageviews |
| `contrarian` | The candidate with the fewest pageviews |
| `homebody` | The candidate sharing the most categories with the current page |

`greedy` and `contrarian` are deterministic given the current page, so their choices are
memoized and their walks eventually cycle.

## The protocol

Every walker starts from the **same** set of randomly drawn pages, at every walk length,
so the comparison is controlled: differences come from the rule and not from where the
walk began. Five walks per walker per length, at lengths 12, 25, 50 and 100.

Four measures over the visit counter:

- **Coverage** — how many distinct pages were reached.
- **Visit entropy** — Shannon entropy in bits of the visit distribution. Low means the
  walker funnels into a few pages, high means visits are spread out.
- **Weighted mean popularity** — mean pageviews of visited pages weighted by visit count,
  i.e. the typical popularity of where the walker spends its time.
- **Cycle length** — for the deterministic walkers, the loop each walk falls into.

Pageviews and categories are fetched once and cached to disk, since walkers query the same
pages repeatedly and the API is the bottleneck.

## Run

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
export WIKI_USER_AGENT="your-project (your-contact)"   # Wikipedia asks for a real UA
./.venv/bin/python main.py
```

Produces three figures:

- `grid_top_pages.png` — most visited pages per walker and length, annotated with entropy
- `trends.png` — coverage, popularity and entropy against walk length
- `cyclicity.png` — distribution of cycle lengths for the deterministic walkers

The first run is slow because it populates the cache; later runs reuse it.

## Limitations

- Five walks per cell is enough to see the ordering between walkers, not to put an error
  bar on it.
- On pages with more than 20 article-space links, candidates are subsampled uniformly at
  random to bound the number of pageview lookups per step. The `greedy` and `contrarian`
  rules are therefore deterministic only through memoization: their first visit to a hub
  page picks from a random subset, and that choice is then reused for the rest of the run.
- Pageview counts are a proxy for popularity and carry their own recency and language bias.
