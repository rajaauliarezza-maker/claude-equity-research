from .kontan import KontanScraper
from .bisnis import BisnisScraper
from .emitennews import EmitenNewsScraper
from .jakartapost import JakartaPostScraper

ALL_SCRAPERS = [
    KontanScraper,
    BisnisScraper,
    EmitenNewsScraper,
    JakartaPostScraper,
]

__all__ = [
    "KontanScraper",
    "BisnisScraper",
    "EmitenNewsScraper",
    "JakartaPostScraper",
    "ALL_SCRAPERS",
]
