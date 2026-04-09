import os, requests, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

API_BASE = 'https://v3.football.api-sports.io'
HEADERS = {'x-apisports-key': os.getenv('API_FOOTBALL_KEY')}

def search(name):
    for league in [140, 39, 61, 78, 135, 307]:
        r = requests.get(f'{API_BASE}/players', headers=HEADERS,
            params={'search': name, 'league': league, 'season': '2024'})
        results = r.json().get('response', [])
        if results:
            p = results[0]
            pid = p['player']['id']
            pname = p['player']['name']
            team = p.get('statistics', [{}])[0].get('team', {}).get('name', '')
            return pid, pname, team
    return None

names = [
    'Lamine Yamal', 'Vitinha', 'Joao Neves', 'Ruben Dias', 'Pedro Neto',
    'Goncalo Ramos', 'Francisco Conceicao', 'Bernardo Silva', 'Joao Felix',
    'Cristiano Ronaldo'
]
for name in names:
    r = search(name)
    print(f'{name}: {r}')
