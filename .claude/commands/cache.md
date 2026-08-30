---
description: Clear Zoo Design Studio's caches when its model index goes bad. Free, offline, no engine.
allowed-tools: Bash(uv run tools/clear_cache.py:*)
---

Clear Design Studio's caches:

```
uv run tools/clear_cache.py $ARGUMENTS
```

Use this when Design Studio opens on stale or missing geometry, shows a model
that does not match the `.kcl` files on disk, or otherwise looks like it is
reading from a corrupted index rather than the sources.

Add `--dry-run` to list what would go without deleting it, and `--all` to take
the session stores too, which signs the user out of their Zoo account. Neither
mode touches `settings.toml`, and nothing here touches the KCL sources.

This costs no API credits and needs no token.

Then:

- If it refuses because Design Studio is running, say so and ask the user to
  close it. Do **not** reach for `--force` on your own: clearing a live profile
  is what makes the next corruption.
- Report in one line what was freed. The app rebuilds all of it on next start,
  so the only cost of a needless run is a slower first load.
- If the corruption comes back quickly, that is worth saying — a cache that
  keeps going bad is a symptom, and repeatedly clearing it only treats the
  symptom.
