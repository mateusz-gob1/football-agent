import re
import time
import requests
from dataclasses import dataclass
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


@dataclass
class PlayerMarketData:
    name: str
    market_value_eur: float | None   # in millions, e.g. 200.0
    contract_expires: str | None     # "YYYY-MM-DD"
    days_until_expiry: int | None


def _parse_market_value(text: str) -> float | None:
    """Parse '€200.00m' or '€50.00k' into float (millions)."""
    text = text.replace("\xa0", "").strip()
    match = re.search(r"([\d.,]+)\s*([mk]?)", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    unit = match.group(2).lower()
    if unit == "k":
        value = value / 1000
    return round(value, 2)


def _parse_contract_date(text: str) -> str | None:
    """Extract contract expiry date — last DD/MM/YYYY in text (after 'Contract expires:')."""
    matches = re.findall(r"(\d{2}/\d{2}/\d{4})", text)
    if not matches:
        return None
    day, month, year = matches[-1].split("/")
    return f"{year}-{month}-{day}"


def get_player_market_data(transfermarkt_url: str, player_name: str) -> PlayerMarketData:
    time.sleep(1)  # polite scraping
    r = requests.get(transfermarkt_url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # market value
    mv_tag = soup.find("a", class_="data-header__market-value-wrapper")
    market_value = _parse_market_value(mv_tag.get_text()) if mv_tag else None

    # contract expiry
    contract_expires = None
    for span in soup.find_all("span", class_="data-header__label"):
        if "contract expires" in span.get_text().lower():
            contract_expires = _parse_contract_date(span.parent.get_text())
            break

    # days until expiry
    days_until_expiry = None
    if contract_expires:
        from datetime import date
        expiry = date.fromisoformat(contract_expires)
        days_until_expiry = (expiry - date.today()).days

    return PlayerMarketData(
        name=player_name,
        market_value_eur=market_value,
        contract_expires=contract_expires,
        days_until_expiry=days_until_expiry,
    )


if __name__ == "__main__":
    players = [
        ("Kylian Mbappe", "https://www.transfermarkt.com/kylian-mbappe/profil/spieler/342229"),
        ("Vinicius Junior", "https://www.transfermarkt.com/vinicius-junior/profil/spieler/371998"),
        ("Pedri", "https://www.transfermarkt.com/pedri/profil/spieler/683840"),
    ]

    for name, url in players:
        data = get_player_market_data(url, name)
        expiry_info = f"{data.contract_expires} ({data.days_until_expiry} days)" if data.contract_expires else "N/A"
        print(f"{data.name}")
        print(f"  Market value: €{data.market_value_eur}M")
        print(f"  Contract expires: {expiry_info}")
        print()
