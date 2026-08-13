# Ogma Print Studio — state of play

**Generated 2026-08-13**, replacing the 2026-08-11 version. Every fact below was
checked against the repo or measured from a running container. Where something
is unverified it says so.

- Branch `oggie-spin`, HEAD `d4b326d`
- **32 commits unpushed.** `origin/main` last moved **2026-07-25** — 19 days ago
- `.git` is 220 MB; `_other-products/` is 457 MB, the dog bowl side ~620 MB
- `_to_delete/` — 2.1 GB — deleted

---

## 0. Do this before anything else

- [ ] **Push.** 32 commits exist on one MacBook and nowhere else.

This has been the top line of every version of this document. It was 4 commits,
then 24, now 32, and it now covers the entire deploy path, the product split and
the whole test harness. It costs ten minutes.

```bash
git push -u origin oggie-spin      # or: git checkout main && git merge oggie-spin && git push
```

- [ ] Decide whether `oggie-spin` is still the working branch, or whether this
      belongs on `main`. Nothing below can start until this is answered.

---

## 1. The repo is now one product

- [x] **Clickers, lamps, Oggie Spin and the Squspi ball moved to
      `_other-products/`**, with a copy of `shared/` so the directory runs
      standalone. See `_other-products/MIGRATION.md`.
- [x] The cut was clean because of the earlier seam work — checked, not assumed:
      nothing outside `products/` imported a product, and no moved product
      imported the dog bowl. They touch the toolkit at one point,
      `ogma.filaments`.
- [x] `_to_delete/` deleted. Three files rescued rather than binned because two
      of them **differ from the tracked copies** by ~448 and ~18 diff lines.
      Parked in `_other-products/_rescued-from-to-delete/`.
- [x] **The tracked-STL question resolved itself.** All 290 tracked `.stl` files
      are under `_other-products/`. The dog bowl side has none — it is a
      question for the other repo now, not this one.
- [ ] `git filter-repo` if you want `.git` back under 220 MB. Moving files
      cleaned the working tree; history still holds every byte.

---

## 2. Bugs found by running it

- [x] **Preview decimation had never once run.** `fast_simplification` was
      missing from requirements.txt, so `simplify_quadric_decimation` raised on
      every call into a bare `except: pass`. Honeycomb and fluted previews were
      489,904 triangles / 8.4 MB against a stated budget of 90k / ~2 MB. Now
      92k / 1.66 MB, and the silent catch logs.
- [x] **CORS matched substrings.** `allow_origins` was handed the raw
      comma-joined string, so Starlette's `origin in allow_origins` was a
      substring test — `http://localhost:300` was granted a header with
      credentials. The parsed list existed and was unused.
- [x] **`smoke_imports.py` was under-reporting.** Results were keyed by module
      *stem*, and two modules share the stem `preview`, so one silently
      overwrote the other's verdict. A broken `ogma.preview` would have reported
      clean.
- [x] **`test_name_fit.py` asserted nothing.** Named `test_*.py` but containing
      only a `main()`, so pytest collected it, found no tests, and passed.
- [x] **The reaper deleted customer files silently.** Root logger defaults to
      WARNING and uvicorn configures only its own, so every `ogma.*` info line
      was dropped.
- [x] Dead ternary in `page.tsx` — `stale ? preview.url : preview.url`.

---

## 3. The deploy path — built and run, not just written

The old config **could not have worked**: `studio/api-Dockerfile` copied `app/
generator/ data/ assets/` and ran `uvicorn app.main:app`, a layout deleted weeks
earlier in `290f64b`; `studio/railway.json` pointed at a file that did not exist.

- [x] `studio/Dockerfile`, built from the repo root, non-root user, `/data`
      volume, `sh -c exec` so SIGTERM reaches uvicorn
- [x] `.dockerignore` — build context 1.3 GB → **7 MB**
- [x] **Web image had three independent faults.** It never copied
      `next.config.ts` into the runner; `PIPELINE_API_URL` could not work as a
      runtime variable because `rewrites()` is baked into `routes-manifest.json`
      at build time; and `npm ci` had never been able to run, because the
      committed lockfile was resolved on macOS and omits Linux-only optional
      deps. All three fixed — the proxy is now a route handler read per request.
- [x] `DEPLOY.md` — two-service layout, why one replica, why the volume matters
- [x] **A 3MF built in the container is byte-identical to one built on macOS**,
      all 34 members, despite trimesh 5.0.0 against 4.12.2. One case
      (`cooper`/`REX`/`bold`) — strong evidence, not proof across every style.
      This is the first actual measurement of the version-drift risk.
- [ ] **Actually deploy it.** Needs a Railway project decision: new, or a
      service inside `responsible-learning`?

---

## 4. Surviving contact with users

- [x] **Retention.** A single completed job leaves **14.1 MB** on the volume,
      measured. Jobs expire by age (`JOB_RETENTION_HOURS`, default 7 days);
      previews evict LRU to a budget (`PREVIEW_CACHE_MAX_MB`, default 512),
      because a preview is pure cache keyed on a geometry hash. In-process, so
      the sweep can skip jobs that are still building.
- [x] Two unbounded leaks closed: `_jobs` held every job ever seen, and the
      limiter's buckets would have mapped every IP ever seen.
- [x] **Rate limiting.** Token bucket per caller on `/generate` and `/preview` —
      the two that take the global build lock. 429 with `Retry-After`. Keyed on
      `x-forwarded-for`, which is only trustworthy while the API has no public
      domain.
- [x] **CI** — imports, unit tests, all five golden cases building, the
      configurator linting and building, and both Docker images.
- [ ] **No authentication.** Anonymous by design for the MVP; the rate limit is
      the only thing between the build lock and the open internet.

---

## 5. Production gates — what actually blocks selling

Unchanged. Nothing in the software list moves any of these.

| Gate | Status | Notes |
|---|---|---|
| G1 slice everything | ✅ | `G1-slice-results.md` |
| **G2** one stand of each style | ⬜ | ~3 print days |
| **G3** load test | ⬜ | **Highest untested risk.** Nothing has been proven to hold a dog's weight |
| G4 adhesive | ⬜ | ~2 h |
| G5 cleanability | ⬜ | ~1 h |
| **G6** source the bowl | ⬜ | **Single point of failure.** Blocks all pricing |
| G7 compliance | ⬜ | ~half a day |
| G8 packaging & instructions | ⬜ | ~1 day |
| G9 repeatability | ⬜ | ~1 print day |

---

## 6. Known risks

- [ ] **Bambu Studio has still never opened a generated 3MF.**
      `tests/audit_3mf.py` passes 14/14 against a P2S profile, which is not the
      same as the slicer accepting the file. Twenty minutes, and the largest
      unverified risk in the whole stack.
- [x] ~~trimesh version drift~~ — measured, see §3. Worth re-checking across the
      other four styles.
- [x] ~~`_union`/`_difference` defined five times~~ — all ten definitions left
      with the moved products. The bowl uses `boolean_union` /
      `boolean_difference`, defined once.
- [ ] `products/dog-bowl/STATUS.md` documents locked *physical* decisions
      (letter sizes, clearances, collar radii) that were earned from real prints
      — those are still authoritative. Its software sections are not.

---

## 7. Next up

Ordered by information gained per hour.

1. **Push**, and settle the branch question
2. **Open a 3MF in Bambu Studio** — the cheapest way to retire the biggest risk
3. **Deploy** — needs the Railway decision, and whether the URL is public or
   gated (that decides whether §4's limits are enough)
4. Re-check the container/macOS geometry match across the other four styles
5. Wire Oggie Spin into the designer *in its new repo* — still the honest test
   of whether the product-spec abstraction earns its keep

### Deferred by decision

- No pricing — machine time dominates and the bowl has no supplier
- No checkout — out of scope until the SKUs are print-proven
