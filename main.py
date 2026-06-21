import logging
import os
from collections import Counter

import matplotlib.pyplot as plt
import wikipediaapi

from cache import PageCache
from explorer import (
    Explorer,
    plot_top_pages,
    visit_entropy,
    coverage,
    weighted_mean_popularity,
    detect_cycle,
    DETERMINISTIC_WALKERS,
    _short,
)
import walkers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

USER_AGENT = os.environ.get("WIKI_USER_AGENT", "explorator (contact via GitHub)")
wiki = wikipediaapi.Wikipedia(user_agent=USER_AGENT)
cache = PageCache(wiki, USER_AGENT)

N_WALKS = 5
WALK_LENGTHS = [12, 25, 50, 100]  # short walks just echo the start page
MAX_CANDIDATES = 20
TOP_N = 8

WALKERS = {
    "drunk": walkers.drunk,
    "greedy": walkers.greedy,
    "contrarian": walkers.contrarian,
    "homebody": walkers.homebody,
}

# same random starts for every walker & length, for a fair comparison
start_titles = list(wiki.random(limit=N_WALKS).keys())

results = {}
for name, fn in WALKERS.items():
    explorer = Explorer(name, fn, cache, max_candidates=MAX_CANDIDATES)
    results[name] = {
        length: explorer.run_experiment(start_titles, length)
        for length in WALK_LENGTHS
    }

figA, axes = plt.subplots(
    len(WALKERS), len(WALK_LENGTHS),
    figsize=(5 * len(WALK_LENGTHS), 3 * len(WALKERS)),
    squeeze=False,
    constrained_layout=True,
)
for row, name in enumerate(WALKERS):
    for col, length in enumerate(WALK_LENGTHS):
        _, counter = results[name][length]
        plot_top_pages(
            counter, top_n=TOP_N, ax=axes[row][col],
            title=f"{name}, len={length}\nentropy={visit_entropy(counter):.2f} bits",
        )
starts_str = "   ·   ".join(_short(t, 28) for t in start_titles)
figA.suptitle(
    f"Top visited pages  (N={N_WALKS} walks per cell)\n"
    f"start pages:  {starts_str}",
    fontsize=12,
)
figA.savefig("grid_top_pages.png", dpi=120)

figB, (ax_cov, ax_pop, ax_ent) = plt.subplots(1, 3, figsize=(15, 4))
for name in WALKERS:
    counters = [results[name][length][1] for length in WALK_LENGTHS]
    ax_cov.plot(WALK_LENGTHS, [coverage(c) for c in counters], "o-", label=name)
    ax_pop.plot(WALK_LENGTHS,
                [weighted_mean_popularity(c, cache) for c in counters],
                "o-", label=name)
    ax_ent.plot(WALK_LENGTHS, [visit_entropy(c) for c in counters], "o-", label=name)
ax_cov.set(title="Coverage", xlabel="walk length", ylabel="distinct pages")
ax_pop.set(title="Avg popularity of visited pages",
           xlabel="walk length", ylabel="mean pageviews (log)")
ax_pop.set_yscale("log")
ax_ent.set(title="Visit concentration", xlabel="walk length", ylabel="entropy (bits)")
for ax in (ax_cov, ax_pop, ax_ent):
    ax.legend(fontsize=8)
figB.tight_layout()
figB.savefig("trends.png", dpi=120)

det_walkers = [n for n in WALKERS if n in DETERMINISTIC_WALKERS]
longest = max(WALK_LENGTHS)
figC, axes_c = plt.subplots(1, len(det_walkers),
                            figsize=(5 * len(det_walkers), 4), squeeze=False)
for col, name in enumerate(det_walkers):
    paths, _ = results[name][longest]
    cyc_lengths = [len(detect_cycle(p) or []) for p in paths]
    dist = Counter(cyc_lengths)
    keys = sorted(dist)
    ax = axes_c[0][col]
    ax.bar([("none" if k == 0 else str(k)) for k in keys], [dist[k] for k in keys])
    ax.set(title=f"{name}  (len={longest})",
           xlabel="cycle length", ylabel="# walks")
figC.suptitle("Cyclicity of deterministic walkers", fontsize=14)
figC.tight_layout()
figC.savefig("cyclicity.png", dpi=120)

plt.show()
