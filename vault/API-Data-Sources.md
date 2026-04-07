# API & Data Sources

## NewsAPI

**Purpose:** Media coverage and sentiment analysis

**Endpoint:** `https://newsapi.org/v2/everything`

**Key parameters:**
- `q` — search query. Always use `"player name"` (quoted) for exact match + optional club name
- `from` — date range start (default: 7 days back)
- `pageSize` — max 100, we use 10 per player
- `language=en` — English articles only
- `sortBy=publishedAt`

**Free tier:** 100 requests/day, articles up to 1 month old

**Returns:** title, url, publishedAt, description, source.name

**Known issues:**
- Less famous players may return 0 results — handled gracefully (no_coverage flag)
- Articles often about the team/match rather than the player specifically — affects sentiment accuracy

---

## Transfermarkt

**Purpose:** Market value and contract expiry date

**Method:** Scraping (no official API)

**Library:** requests + BeautifulSoup

**Key data points:**
- Current market value (€)
- Market value history (trend)
- Contract expiry date
- Current club

**Limitations:** Scraping can break if Transfermarkt changes their HTML structure. Rate limiting — add delays between requests.

---

## API-Football (api-sports.io)

**Purpose:** Player match statistics

**Base URL:** `https://v3.football.api-sports.io`

**Key endpoints:**
- `GET /players?id={id}&season={year}` — season stats (goals, assists, minutes, ratings)
- `GET /players?search={name}&league={id}` — search player by name

**Free tier:** 100 requests/day — cache everything locally

**Caching strategy:** Store stats as JSON, refresh once per system run (weekly briefing = weekly refresh)

**Returns per player:** appearances, goals, assists, minutes played, average rating, shots, passes, dribbles, cards

**Registration:** api-sports.io (free account, no credit card)
