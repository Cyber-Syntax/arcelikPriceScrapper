## The "0 products" lines

You pasted only the zero lines, so I can't tell whether `mini-buzdolabi` worked. Check that first:

```bash
uv run arcelikPriceScrapper 2>&1 | grep -E 'mini-buzdolabi|smart-tv|HTTP|ERR'
```

Names like `4k-android-tv` and `4k-quantum-dot-tv` look like **sub-filters of `smart-tv`**. Sitemap URLs use them as a path segment, but `/4k-android-tv` probably isn't a listing page. It may 404 or redirect. Test one directly:

```bash
uv run python -c "
from curl_cffi import requests as r
for slug in ('mini-buzdolabi', '4k-android-tv'):
    x = r.get(f'https://www.arcelik.com.tr/{slug}', impersonate='chrome')
    print(slug, x.status_code, x.url, x.text.count('prd-inner'))"
```

- **`mini-buzdolabi` gives 24 or more cards:** the approach works, and the zeros are just non-listing slugs. That's harmless, but each one wastes about 2 requests, so skip them.
- **`mini-buzdolabi` also gives 0 (200 status):** the pagination or card loading is different from what I assumed. Paste that output.

## Runtime

I can't measure it from here, so this is an estimate. 5,630 products at around 24 cards per page is about 235 pages minimum. Products appearing in several categories, plus one terminating request per category, push it to roughly 700–1,000 requests. At concurrency 2 with 0.5–1.5 s delays, that's about **15–40 minutes**. Run it once as a test, since the disk cache below makes reruns cheap.

## Avoiding a ban

Akamai watches request rate, patterns and fingerprint consistency. The conservative approach:

1. **Low and steady rate.** Use `SEM = 1` or `2` and delays of 1–3 s. At that rate this job is a single polite session.
2. **Reuse one session.** You already do. The cookies Akamai sets stay valid across requests.
3. **Cache every response to disk.** A rerun or a parser fix then costs zero requests.
4. **Stop on repeated blocks.** If you get a few 403/429s in a row, stop and wait. Retrying harder is what turns a rate limit into a ban.
5. **Run off-peak** (night, Turkish time) and don't run it more than once or twice a day.
6. **Skip junk categories** (the zero-result ones) instead of retrying them.

I'd avoid rotating proxies or spoofing identities to get around a block. If you do get blocked, wait and slow down rather than work around it. If you need this at higher volume or frequency, ask Arçelik whether they have a feed.

## Code changes

```python
import hashlib, pathlib

CACHE = pathlib.Path(".cache"); CACHE.mkdir(exist_ok=True)
SEM = asyncio.Semaphore(1)
BLOCKS = 0
MAX_BLOCKS = 5


async def get(session, url, retries=3):
    global BLOCKS
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if f.exists():
        return f.read_text(encoding="utf-8")
    for attempt in range(retries):
        if BLOCKS >= MAX_BLOCKS:
            raise SystemExit("Too many 403/429, stopping. Wait before retrying.")
        async with SEM:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            try:
                r = await session.get(url)
            except Exception as e:
                print(f"ERR {type(e).__name__} {url[:100]}", file=sys.stderr)
                r = None
        if r is not None:
            if r.status_code == 200:
                BLOCKS = 0
                f.write_text(r.text, encoding="utf-8")
                return r.text
            print(f"HTTP {r.status_code} {url[:100]}", file=sys.stderr)
            if r.status_code in (403, 429):
                BLOCKS += 1
            elif r.status_code < 500:
                return None
        await asyncio.sleep(2 ** attempt * 5)
    return None
```

Note that `BLOCKS` is a global counter, which is fine for a single script like this.

In `amain`, replace the `asyncio.gather` over categories with a plain loop:

```python
for s in slugs:
    await crawl_listing(client, s, found)
```

I'd also drop zero-result slugs from future runs. After the first run, write the slugs that returned cards to a `categories.txt` file and load that next time.

Send me the output of the two checks above (`mini-buzdolabi` and `4k-android-tv`), plus the `HTTP`/`ERR` lines if any appear. Then I can tell whether the zeros are just non-listing slugs or whether pagination needs fixing, and I can help with discovering categories from the hub pages.
