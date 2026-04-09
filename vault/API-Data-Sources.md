# API & Data Sources

## NewsAPI

**Purpose:** Media coverage and sentiment analysis input.

**Endpoint:** `https://newsapi.org/v2/everything`

**Key parameters:**
- `q` — search query. Always use `"player name"` (quoted) for exact match. Optional: append club name for disambiguation (e.g. `"Pedro Neto" Chelsea`)
- `from` — date range start (default: 7 days back)
- `pageSize` — max 100, system uses 10 per player
- `language=en` — English articles only
- `sortBy=publishedAt`

**Free tier:** 100 requests/day, articles up to 1 month old.

**Returns:** title, url, publishedAt, description, source.name

**Data class:** `Article(title, url, published_at, description, source)`

**Entry point:** `fetch_player_news(player_name, club=None, days_back=7)` in `tools/news_fetcher.py`

**Known issues:**
- Less famous players may return 0 results — handled gracefully via `no_coverage` flag
- Articles often cover the team or match rather than the player specifically — affects sentiment accuracy for secondary-role players

---

## Transfermarkt

**Purpose:** Market value, contract expiry, season stats per competition, market value history.

**Method:** Web scraping — no official API exists.

**Library:** Playwright (Chromium, headless) — migrated from cloudscraper on 2026-04-09.

### Functions

| Function | URL pattern | Returns |
|---|---|---|
| `get_player_market_data()` | `/profil/spieler/{id}` | Current market value (€), contract expiry date, current club |
| `get_season_stats()` | `/leistungsdaten/spieler/{id}` | Appearances, goals, assists, minutes per competition |
| `get_market_value_history()` | `/marktwertverlauf/spieler/{id}` | Historical market value with dates |

### URL Structure

```
Profile:       https://www.transfermarkt.com/{name}/profil/spieler/{id}
Season stats:  https://www.transfermarkt.com/{name}/leistungsdaten/spieler/{id}
Value history: https://www.transfermarkt.com/{name}/marktwertverlauf/spieler/{id}
```

The `{id}` is the numeric Transfermarkt player ID. This must be copied from the player's profile URL in a browser — never guessed or constructed.

### Cloudflare Bypass

Playwright with Chromium (headless) launches a real browser for each fetch. Shares a module-level browser instance across all requests in a pipeline run (one launch, many contexts). Each request gets a fresh browser context (isolated cookies/headers).

**Configuration:** Chrome UA, `locale=en-US`, `viewport=1280×800`, `wait_until="networkidle"` — gives Cloudflare time to resolve the challenge before the HTML is captured.

**Known limitation:** Cloudflare Turnstile ("Let's confirm you are human") still blocks headless Playwright during testing. This affects `leistungsdaten` and `marktwertverlauf` pages but not always `profil`. Contract data for the demo is sourced from Capology as fallback.

**Setup:** After `pip install playwright`, run `playwright install chromium` once.

### Rate Limiting

- 2-second sleep between requests (in `_fetch()`)
- Production cadence (weekly, ~10 players) is safe
- Aggressive scraping (30+ rapid requests) will trigger Cloudflare blocking

### Player ID Verification

The `transfermarkt_url` field on the Player dataclass must be set manually. Copy the full URL from the browser when viewing the player's profile on transfermarkt.com. This is the only reliable way to guarantee the correct player is tracked — name-based search is ambiguous and rate-limited.

**Format:** `https://www.transfermarkt.com/{slug}/profil/spieler/{id}`

**Example:** `https://www.transfermarkt.com/lamine-yamal/profil/spieler/927130`

### Future: Playwright Migration

Planned as next-step improvement. Full browser execution via Playwright will:
- Eliminate 405 Turnstile errors
- Support JS-rendered content
- Enable more reliable session management for extended scraping sessions

---

## API-Football (api-sports.io)

**Purpose:** Player match statistics — goals, assists, minutes, average rating.

**Current usage note:** Free tier covers seasons 2022–2024 only. Season 2025/26 stats for the demo are sourced from Transfermarkt screenshots (manual entry). API-Football is used for historical cache only.

**Base URL:** `https://v3.football.api-sports.io`

**Key endpoints:**
- `GET /players?id={id}&season={year}` — season stats for a known player ID
- `GET /players?search={name}&league={id}` — search player by name

**Free tier:** 100 requests/day. Cache everything locally to stay within limit.

**Caching strategy:** Stats stored as JSON in `data/stats_cache/`. Refreshed once per system run (weekly briefing = weekly cache refresh). Cache key: `{player_id}_{season}`.

**Returns per player:** appearances, goals, assists, minutes played, average rating, shots, passes, dribbles, cards.

**Player ID resolution:** `add_player()` in `tools/player_store.py` auto-resolves the API-Football ID from player name + club at registration time.

**Note:** API-Football is the primary stats source. FBref (via `soccerdata`) is a secondary/fallback source added in Block 3 for richer data (xG, xAG) and seasons where API-Football cache is stale.

**See also:** `tools/fbref_fetcher.py`

**Registration:** api-sports.io — free account, no credit card required.

---

## FBref (via soccerdata)

**Purpose:** Secondary/fallback source for player season statistics. Richer than API-Football — includes xG, xAG, progressive carries, pressing stats.

**Method:** `soccerdata` Python library scrapes fbref.com and caches HTML locally in `~/soccerdata/data/FBref/`.

**Entry point:** `get_player_stats(player_name, club, season)` in `tools/fbref_fetcher.py`

**When used:**
- API-Football player ID not found
- Richer stats needed for briefing context (xG, advanced metrics)
- RAGAS evaluation pipeline (controlled dataset)

**Supported leagues:** ENG-Premier League, ESP-La Liga, FRA-Ligue 1, ITA-Serie A, GER-Bundesliga

**Rate limit:** ~7 seconds between requests (enforced automatically by soccerdata). First call per league/season takes 10–30s; subsequent calls use local cache and are instant.

**Returns:** appearances (MP), goals (Gls), assists (Ast), minutes (Min), xG, xAG

**Key constraint:** League-level query only — returns all players in a league, filtered by name. Not player-centric like API-Football.

**Installation:** `pip install soccerdata`

---

## Capology

**Purpose:** Player salary estimates and contract expiry dates. Only public source for football wages.

**Method:** Playwright scraper (Chromium) — same browser infrastructure as Transfermarkt scraper. ScraperFC's Capology module was available but uses Selenium; we use Playwright for consistency.

**Entry point:** `get_player_contract(player_name, club, season)` in `tools/capology_fetcher.py`

**Returns per player:**
- `weekly_eur` — estimated gross weekly salary in EUR
- `annual_eur` — estimated gross annual salary in EUR
- `contract_signed` — ISO date the current contract was signed
- `contract_expires` — ISO date contract ends
- `years_remaining` — full seasons left

**Caching:** Full league scrape cached in `data/capology_cache/{league}_{season}.json`. Re-fetch not needed within the same season unless a transfer occurs.

**Supported leagues:** ENG-Premier League, ESP-La Liga, FRA-Ligue 1, ITA-Serie A, GER-Bundesliga, POR-Primeira Liga, SAU-Saudi Pro League

**Salary accuracy:** Capology labels all figures as estimates. Actual contract values including bonuses and image rights are not public.

**Verified data (2025-26 season, tested 2026-04-09):**
- Bernardo Silva (Man City): €300k/week, expires 2026-06-30 ✅ (matches TM data)
- Lamine Yamal (Barcelona): €320k/week, expires 2031-06-30
- Vitinha (PSG): €227k/week, expires 2029-06-30
- Cristiano Ronaldo (Al-Nassr): Saudi Pro League covered ✅
