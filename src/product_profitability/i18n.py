"""
Words shown to people in two languages: English for the app and the public README, Polish for the README while the
repository is private. Category and colour names follow Data-Generator's settings/localization.py.
"""
from __future__ import annotations

LANGUAGES = ("en", "pl")

STEP_LABELS = {
    "en": {"list_margin": "Price-list margin", "discount": "Discounts", "returns": "Returns", "shipping": "Shipping",
           "payment": "Payment fees", "commission": "Affiliate commission", "true_margin": "True margin"},
    "pl": {"list_margin": "Marża z cennika", "discount": "Rabaty", "returns": "Zwroty", "shipping": "Wysyłka",
           "payment": "Opłaty za płatność", "commission": "Prowizja afiliacyjna", "true_margin": "Marża na czysto"},
}
MOVE_LABELS = {
    "en": {"price": "Change the price", "free_shipping": "End free delivery", "delist": "Delist"},
    "pl": {"price": "Zmień cenę", "free_shipping": "Bez darmowej dostawy", "delist": "Wycofaj"},
}
DRIVER_LABELS = {
    "en": {"price_list": "price below cost", "discount": "discounts", "returns": "returns", "shipping": "shipping",
           "payment": "payment fees", "commission": "affiliate commission"},
    "pl": {"price_list": "cena poniżej kosztu", "discount": "rabaty", "returns": "zwroty", "shipping": "wysyłka",
           "payment": "opłaty za płatność", "commission": "prowizja afiliacyjna"},
}
CATEGORIES_PL = {
    "Electronics": "Elektronika", "Clothing": "Odzież", "Home & Garden": "Dom i ogród", "Sports": "Sport",
    "Beauty": "Uroda", "Toys": "Zabawki", "Automotive": "Motoryzacja", "Books & Media": "Książki i media",
    "Health": "Zdrowie", "Pet Supplies": "Artykuły dla zwierząt", "Baby & Kids": "Dziecko", "Office": "Biuro",
    "Jewelry & Accessories": "Biżuteria i akcesoria", "Furniture": "Meble", "DIY Tools": "Narzędzia",
}
COLORS_PL = {
    "black": "czarny", "white": "biały", "gray": "szary", "silver": "srebrny", "blue": "niebieski",
    "navy": "granatowy", "red": "czerwony", "green": "zielony", "beige": "beżowy", "brown": "brązowy",
    "pink": "różowy", "yellow": "żółty", "orange": "pomarańczowy", "purple": "fioletowy", "gold": "złoty",
    "multicolor": "wielokolorowy",
}
MONTHS_PL = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def category(name: str, language: str = "en") -> str:
    return CATEGORIES_PL.get(name, name) if language == "pl" else name


def color(name: str, language: str = "en") -> str:
    return COLORS_PL.get(name, name) if language == "pl" else name


def month(stamp, language: str = "en") -> str:
    """'Jan 2023' or 'sty 2023'."""
    return f"{MONTHS_PL[stamp.month - 1]} {stamp.year}" if language == "pl" else f"{stamp:%b %Y}"


def plural_pl(count: int, one: str, few: str, many: str) -> str:
    """
    The Polish word that agrees with a count: 1 -> one, 2-4 (also 22-24, but not 12-14) -> few, else many.
    `plural_pl(44, "traci", "tracą", "traci")` gives "tracą" for "44 z 500 bestsellerów tracą".
    """
    count = abs(int(count))
    if count == 1:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


def check(language: str) -> str:
    if language not in LANGUAGES:
        raise ValueError(f"Unknown language {language!r}; use one of {', '.join(LANGUAGES)}")
    return language
