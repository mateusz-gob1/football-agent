"""
Fetch real season stats for all demo portfolio players.
Uses known league IDs, one request per player, 7s delay between calls.
Results go directly into data/demo_data.json.
"""
import os, requests, time, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

API_BASE = 'https://v3.football.api-sports.io'
HEADERS = {'x-apisports-key': os.getenv('API_FOOTBALL_KEY')}
CACHE_DIR = Path('data/stats_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# player_id → (display_name, league_id, season)
SEASON = 2025  # 2025/26 — current season as of April 2026

# Known IDs from previous search (no API call needed)
PLAYERS = {
    386828: ('Lamine Yamal',        140, SEASON),  # La Liga
    128384: ('Vitinha',             61,  SEASON),  # Ligue 1
    335051: ('Joao Neves',          61,  SEASON),  # Ligue 1
    567:    ('Ruben Dias',          39,  SEASON),  # PL
    1864:   ('Pedro Neto',          39,  SEASON),  # PL
    41585:  ('Goncalo Ramos',       61,  SEASON),  # Ligue 1
    161585: ('Francisco Conceicao', 135, SEASON),  # Serie A
    636:    ('Bernardo Silva',      39,  SEASON),  # PL
    583:    ('Joao Felix',          39,  SEASON),  # PL
    874:    ('Cristiano Ronaldo',   307, SEASON),  # Saudi
}

SEARCH_LIST = []  # all IDs already known

MAJOR = {140, 39, 61, 78, 135, 307}

def get_stats(player_id, season=2025):
    cache_file = CACHE_DIR / f'{player_id}_{season}.json'
    if cache_file.exists():
        print(f'  [cache] {player_id}')
        return json.loads(cache_file.read_text())

    time.sleep(7)
    r = requests.get(f'{API_BASE}/players', headers=HEADERS,
        params={'id': player_id, 'season': season})
    data = r.json()
    if data.get('errors'):
        print(f'  [error] {data["errors"]}')
        return None

    resp = data.get('response', [])
    if not resp:
        return None

    p = resp[0]
    stats_list = p.get('statistics', [])
    best = None
    best_apps = -1
    for s in stats_list:
        lid = s.get('league', {}).get('id')
        apps = s.get('games', {}).get('appearences') or 0
        if lid in MAJOR and apps > best_apps:
            best = s
            best_apps = apps
    if not best and stats_list:
        best = stats_list[0]
    if not best:
        return None

    result = {
        'player_id': player_id,
        'name': p['player']['name'],
        'season': season,
        'appearances': best['games'].get('appearences') or 0,
        'goals': best['goals'].get('total') or 0,
        'assists': best['goals'].get('assists') or 0,
        'minutes': best['games'].get('minutes') or 0,
        'rating': float(best['games']['rating']) if best['games'].get('rating') else None,
        'league': best['league'].get('name', ''),
        'team': best['team'].get('name', ''),
    }
    cache_file.write_text(json.dumps(result))
    return result


def search_player(name, league_id, season=2025):
    time.sleep(7)
    r = requests.get(f'{API_BASE}/players', headers=HEADERS,
        params={'search': name, 'league': league_id, 'season': season})
    data = r.json()
    if data.get('errors'):
        print(f'  [error searching {name}] {data["errors"]}')
        return None
    resp = data.get('response', [])
    if resp:
        return resp[0]['player']['id']
    return None


all_ids = {name: pid for pid, (name, _, _) in PLAYERS.items()}
print('Using known IDs:', all_ids)

print('\n=== Fetching stats ===')
stats_map = {}
for name, pid in all_ids.items():
    print(f'Fetching {name} (ID {pid}) season {SEASON}...')
    s = get_stats(pid, SEASON)
    if s:
        stats_map[name] = s
        print(f'  {s["league"]} | {s["appearances"]} apps | {s["goals"]}g {s["assists"]}a | rating {s["rating"]}')
    else:
        print(f'  no stats')

print('\n=== Updating demo_data.json ===')
demo_path = Path('data/demo_data.json')
demo = json.loads(demo_path.read_text())

updated = 0
for p in demo['players']:
    name = p['name']
    s = stats_map.get(name)
    if s:
        p['rating'] = s['rating']
        p['appearances'] = s['appearances']
        p['goals'] = s['goals']
        p['assists'] = s['assists']
        p['league'] = s['league']
        updated += 1
        print(f'  Updated {name}: rating={s["rating"]}, apps={s["appearances"]}, goals={s["goals"]}, assists={s["assists"]}')
    else:
        print(f'  SKIPPED {name} (no data)')

demo_path.write_text(json.dumps(demo, indent=2, ensure_ascii=False))
print(f'\nDone. Updated {updated}/10 players.')
