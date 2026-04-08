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

**Library:** cloudscraper (handles Cloudflare JS challenges)

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

cloudscraper handles standard Cloudflare JS challenges automatically. No configuration needed for most pages.

**Known limitation:** Cloudflare Turnstile (returns HTTP 405) requires real browser execution. cloudscraper cannot solve it. When this occurs, the scrape fails for that page.

**Mitigation:** Accept occasional failures. The system is designed for weekly runs — a missed scrape is retried the following week. Future fix: migrate to Playwright for full browser automation.

### Rate Limiting

Findings from testing:
- ~10 rapid requests trigger a Cloudflare block
- Production cadence: 10–12 players/week with 2-second delays between requests — does not trigger the block
- The schnellsuche (search) endpoint is also rate-limited — do not use for ID resolution at scale

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

**Base URL:** `https://v3.football.api-sports.io`

**Key endpoints:**
- `GET /players?id={id}&season={year}` — season stats for a known player ID
- `GET /players?search={name}&league={id}` — search player by name

**Free tier:** 100 requests/day. Cache everything locally to stay within limit.

**Caching strategy:** Stats stored as JSON in `data/stats_cache/`. Refreshed once per system run (weekly briefing = weekly cache refresh). Cache key: `{player_id}_{season}`.

**Returns per player:** appearances, goals, assists, minutes played, average rating, shots, passes, dribbles, cards.

**Player ID resolution:** `add_player()` in `tools/player_store.py` auto-resolves the API-Football ID from player name + club at registration time.

**Note:** As of Block 2, Transfermarkt's `get_season_stats()` also provides season stats per competition. API-Football remains in use for match rating data, which TM does not provide.

**Registration:** api-sports.io — free account, no credit card required.
