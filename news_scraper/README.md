# Indonesian Equity News Scraper

Scrapes headlines and summaries from **Kontan**, **Bisnis Indonesia**, **Emitennews**, and **Jakarta Post**. Filters articles by corporate-action keywords, classifies them by IDX sector, and stores everything in a local SQLite database.

## Covered keywords (auto-flagged)

| Keyword | Meaning |
|---|---|
| right issue / rights issue / PMHMETD | Rights offering |
| buyback / buy back | Share buyback |
| akuisisi | Acquisition |
| borong | Bulk insider buying |
| lego | Stake sell-off |
| suntik modal / injeksi modal | Capital injection |
| divestasi | Divestiture |
| merger / take over / tender offer | M&A events |
| PMTHMETD | Non-rights placement |
| stock split / pemecahan saham | Share split |
| delisting / go private | De-listing events |

## Sectors detected

`Perbankan` · `Asuransi & Keuangan` · `Pertambangan` · `Energi & Migas` · `Properti & Real Estate` · `Infrastruktur` · `Teknologi & Telekomunikasi` · `Konsumer & Ritel` · `Farmasi & Kesehatan` · `Agrikultur & Perkebunan` · `Manufaktur & Industri` · `Transportasi & Logistik` · `Media & Hiburan`

---

## Setup

```bash
cd news_scraper
pip install -r requirements.txt
```

---

## Usage

### Scrape all sources
```bash
python -m news_scraper run
```

### Scrape a single source
```bash
python -m news_scraper run --source kontan
python -m news_scraper run --source bisnis
python -m news_scraper run --source emitennews
python -m news_scraper run --source jakartapost
```

### Query flagged articles (last 7 days)
```bash
python -m news_scraper query --flagged
```

### Filter by sector
```bash
python -m news_scraper query --sector Perbankan --flagged
python -m news_scraper query --sector Pertambangan --days 14
```

### Filter by keyword
```bash
python -m news_scraper query --keyword akuisisi --verbose
python -m news_scraper query --keyword "right issue" --days 30
```

### Database statistics
```bash
python -m news_scraper stats
```

### Export flagged articles to CSV
```bash
python -m news_scraper export --output flagged_$(date +%Y%m%d).csv
python -m news_scraper export --all --days 30 --output full_30d.csv
```

---

## Automate with cron

Run every 30 minutes during market hours (WIB, UTC+7):

```cron
# Scrape Mon-Fri 08:00–17:00 WIB every 30 min
*/30 1-10 * * 1-5 cd /path/to/claude-equity-research && python -m news_scraper run >> logs/scraper.log 2>&1
```

---

## Database location

SQLite file is stored at `news_scraper/news.db` by default.
Override with the `NEWS_DB_PATH` environment variable:

```bash
NEWS_DB_PATH=/data/equity_news.db python -m news_scraper run
```

---

## Database schema

```sql
articles (
    id              INTEGER PRIMARY KEY,
    source          TEXT,       -- e.g. "Kontan"
    title           TEXT,
    summary         TEXT,
    url             TEXT UNIQUE,
    published_at    TEXT,       -- ISO-8601
    scraped_at      TEXT,       -- ISO-8601
    keywords_matched TEXT,      -- JSON array
    sector          TEXT,       -- IDX sector label
    ticker          TEXT,       -- 4-letter IDX code if detected
    is_flagged      INTEGER     -- 1 if keyword matched
)
```
