import os, requests, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

API_BASE = 'https://v3.football.api-sports.io'
HEADERS = {'x-apisports-key': os.getenv('API_FOOTBALL_KEY')}

# Check quota first
r = requests.get(f'{API_BASE}/status', headers=HEADERS)
print("Status:", r.json())

# Try searching Ruben Dias directly without league
time.sleep(1)
r = requests.get(f'{API_BASE}/players', headers=HEADERS,
    params={'search': 'Ruben Dias', 'season': '2024'})
print("\nRuben Dias search:", r.json().get('response', [])[:2])
