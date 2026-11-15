# Brand Monitoring

The existing Streamlit dashboard remains available with `streamlit run app.py`.
The new FastAPI service uses PostgreSQL, SQLAlchemy, Alembic migrations, and
JWT authentication.

## Run the API with Docker

Set `JWT_SECRET_KEY` to a long random value, then run:

```shell
docker compose up --build
```

The API is available at `http://localhost:8000`, with interactive OpenAPI
documentation at `/docs`.

Start the Streamlit frontend in a second terminal:

```shell
python -m streamlit run app.py
```

The frontend prompts for the FastAPI account created through `/auth/register`
or `/auth/login`. Reddit mentions, dashboard data, and analysis updates then
use FastAPI and PostgreSQL through HTTPX.

For reliable Reddit access, create a read-only application at
`https://www.reddit.com/prefs/apps` and add these values to `.env`:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=BrandMonitoring/1.0 (your contact)
```

The app uses PRAW with these credentials and only uses public HTTP fallbacks
when credentials are not configured or a provider is unavailable.

Alternatively, configure Apify as the primary Reddit provider:

```env
APIFY_TOKEN=your_apify_token
APIFY_ACTOR_ID=automation-lab~reddit-scraper
APIFY_MAX_ITEMS=25
```

Apify is called through its synchronous dataset API. Keep the token private
and check the actor's current pricing and data-use terms before use.

## Local API development

Set `DATABASE_URL` to a PostgreSQL connection string and run:

```shell
alembic upgrade head
uvicorn backend.main:app --reload
```

Register with `POST /auth/register`, obtain a token with
`POST /auth/login` (`username` is the email), and send it as a bearer token
to the `/mentions` endpoints. `api_client.py` contains a small HTTPX client
for Streamlit integrations.

## Quality checks

```shell
ruff check .
pytest -q
```

The SQLite database is retained only as legacy data for the current dashboard;
new API data is stored in PostgreSQL and managed through Alembic.
