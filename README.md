# Daily Global Tech News Scheduler

A beginner-friendly Python project that will collect technology news, store
articles in MongoDB, and create a daily briefing. The project is being built
step by step so learners can understand each part before moving on.

## Project objective

The finished application will collect articles from a configured news provider,
organize them by technology topic, avoid duplicates using each article's URL,
and save a concise daily briefing. A small REST API will let readers browse and
search the saved information.

## Technologies

- Python
- Flask for REST API endpoints
- Requests for news API calls
- PyMongo for MongoDB
- APScheduler for the daily run
- `python-dotenv` for local environment-variable configuration
- Postman and MongoDB Compass for testing and inspection

## Current stage

Steps 2 and 3 set up Python dependencies, application configuration, and the
MongoDB connection with unique indexes. Step 4 adds editable keyword-based
news categorization. Step 5 fetches and stores articles from GNews. Step 6
ranks recent stories and generates a stored daily briefing. A local Flask
dashboard lets you fetch news, configure automatic refresh intervals, and view
saved articles and briefings. A public API is not implemented.

## Installation

Use Python 3.10 or newer. From the project folder, create a virtual
environment and install the dependencies. Activation is optional; invoking
`.venv\Scripts\python.exe` directly works even when PowerShell script execution
is disabled:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

To activate only for the current PowerShell window instead, you can temporarily
allow the activation script for this process, then activate the environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The process-scoped setting ends when you close that PowerShell window. You do
not need to change the machine-wide execution policy.

## Environment variables

Copy `.env.example` to `.env`, add your GNews API key, and edit other values
for your machine. Keep `.env` private; Git ignores it. The example file
contains placeholders and is safe to share.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MONGODB_URI` | MongoDB connection address | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `tech_news` |
| `NEWS_API_URL` | GNews search endpoint | `https://gnews.io/api/v4/search` |
| `NEWS_API_KEY` | GNews API key | Empty |
| `NEWS_REQUEST_TIMEOUT_SECONDS` | Maximum wait for a news request | `15` |
| `NEWS_SCHEDULE_HOUR` | Daily run hour, from 0 to 23 | `6` |
| `NEWS_SCHEDULE_MINUTE` | Daily run minute, from 0 to 59 | `0` |
| `NEWS_SCHEDULE_TIMEZONE` | Timezone used for the daily schedule | `UTC` |
| `APP_HOST` | Address used by the local API server | `127.0.0.1` |
| `APP_PORT` | Port used by the local API server | `5000` |

The schedule is 6:00 AM in `NEWS_SCHEDULE_TIMEZONE`; change the timezone if
you want the job to run at 6:00 AM in a different region.

## Configuration check

Once dependencies are installed and `.env` is in place, check that Python can
load the settings:

```powershell
py -c "import config; print(config.MONGODB_DATABASE, config.NEWS_SCHEDULE_HOUR, config.NEWS_SCHEDULE_MINUTE, config.NEWS_SCHEDULE_TIMEZONE)"
```

The configuration check only reads settings; the MongoDB connection is covered
in the next section.

## MongoDB setup

Install MongoDB Community Server and start the MongoDB service, or use a
MongoDB Atlas connection URI in your private `.env` file. MongoDB Compass can
connect to the same URI so you can inspect the database visually.

The `database.py` module pings MongoDB before use, selects the database named by
`MONGODB_DATABASE`, and creates these collections' unique indexes:

- `news.url` - prevents the same article URL from being inserted more than
  once.
- `daily_briefings.briefing_date` - reserves one briefing document per date.

MongoDB creates the database and collections when an index is first created or
data is written. Existing duplicate values can prevent MongoDB from creating a
unique index, so resolve duplicates before using this setup with pre-existing
data.

## News categories

`models.py` keeps the editable `CATEGORY_KEYWORDS` dictionary and the
`categorize_news()` function. The function checks the article title and
description, ignoring letter case, and returns the first category with a
matching keyword. The category order is intentional: for example, Agentic AI
is checked before the broader AI category. Articles with no matching keywords
are assigned to `Other Technology`.

This is a simple starting point, not a machine-learning classifier. Add or
remove keywords in `CATEGORY_KEYWORDS` as you observe which terms appear in
your chosen news source.

## Fetching and saving news

Create a GNews account and copy its API key into your local `.env` as
`NEWS_API_KEY`; keep that file private. The fetcher in `news_service.py`
requests the configured GNews endpoint with the key as the `apikey` parameter.
It requests up to 10 recent English-language articles matching a technology
query per request, for compatibility with GNews' free
plan. Review GNews' current plan, coverage, and usage limits before relying
on repeated or scheduled requests.

The service checks HTTP and JSON responses, skips removed or incomplete
articles, and maps provider fields to the project's article fields. It stores
publication and collection times as MongoDB-compatible dates. `save_news()`
inserts articles one at a time: a duplicate URL is ignored by the unique index,
while other database errors are reported.

Fetching requires a configured API key, and saving requires a live MongoDB
connection.

## Run the current pipeline

From the project folder, install dependencies, create your local settings file,
and add your GNews API key to `.env`. These commands do not require activating
the virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If `.env` already exists, do not overwrite it with `Copy-Item`; edit it and
set `NEWS_API_KEY` to your GNews key. Start your local MongoDB service (or set
`MONGODB_URI` in `.env` to your MongoDB Atlas connection URI), then fetch
articles, save them, and generate today's briefing with:

```powershell
.\.venv\Scripts\python.exe -c "from database import connect_to_database; from news_service import fetch_news, save_news; from briefing_service import generate_daily_briefing; client, db = connect_to_database(); print('Saved articles:', save_news(fetch_news(), db.news)); briefing = generate_daily_briefing(db.news, db.daily_briefings); print(briefing['text']); client.close()"
```

Run the automated tests (they use mocked provider and database calls and do not
need a GNews key or live MongoDB server) with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Run the dashboard

Start MongoDB and confirm your GNews API key is set in `.env`. From the
project folder, start the local dashboard:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard) in
your browser. Select a refresh interval (**1 minute**, **5 minutes**,
**1 hour**, or **1 day**) and click **Start automatic refresh**. The dashboard
fetches news immediately, then repeats at the selected interval, saving new
articles and updating the briefing. Keep the Flask app running; updates
continue without further clicks, and an open dashboard refreshes after each
scheduled update. Use **Fetch once** for a single update or **Stop schedule**
to stop recurring fetches. The scheduler is in memory, so stopping the app
also stops the schedule; start it again from the dashboard when needed.

### Test this step

Run the focused automated tests from the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests use mocked HTTP responses and MongoDB inserts, so they do not require
a real API key or running database.

Common problems include a missing or invalid GNews key, an account limit
or HTTP error, a request timeout, malformed JSON, and MongoDB being stopped.
The service reports safe, readable errors for these cases; an empty article
list is valid and results in zero inserts.

## Daily briefing and story scoring

`briefing_service.py` looks up articles published within the last 24 hours.
Each story gets a transparent score:

- Start with a category score: Agentic AI and Quantum Computing score 7; AI
  and Cybersecurity 6; Cloud 5; Startups and Technology Companies 4;
  Programming and Developer Tools 3; Other Technology 1.
- Add 2 if the title or description contains one or more configured impact
  terms such as `critical`, `vulnerability`, `breakthrough`, or `funding`.
- Add freshness points: 4 if published in the last 6 hours, 3 between 6 and
  12 hours, or 1 between 12 and 24 hours.

The highest-scoring stories are selected, with duplicate URLs removed. The
briefing groups stories into readable topic sections, uses the provider's
description as its summary, and adds a simple rule-based “why it matters,”
learning topic, and career-skills suggestion. It does not invent or
AI-generate article summaries.

The service stores a date-keyed briefing with `replace_one(..., upsert=True)`.
This means rerunning the job for a date updates that day's briefing rather
than creating another one. The unique `daily_briefings.briefing_date` index
provides an additional database-level safeguard.

### Test this step

Run all focused service tests:

```powershell
py -m unittest discover -s tests -v
```

The tests use mock MongoDB collections, so they don't need a running MongoDB
server. The briefing reads recent news sorted by publication date, ranks it
deterministically, and stores one briefing document per configured local date.

Common limitations: importance ranking is only a transparent heuristic,
provider descriptions may be short, and stories with missing publication dates
are not included in the 24-hour database query. A live briefing requires
articles to have already been collected.
