# USQuery

> **This repository is a public snapshot, not the live codebase.** It is
> published periodically from a private repository to showcase the project's
> structure, test suite and CI/CD pipeline. Proprietary components (the
> retrieval-augmented bill chat, the vote-prediction model, the bill-status
> timeline engine, search ranking and some data pipelines) are replaced with
> stubs that keep the same interfaces. This snapshot is never deployed, and
> pull requests are not merged here.

USQuery is a web application designed to provide users with easy access to congressional data, including bills and votes. The live site is [usquery.com](https://www.usquery.com).

## Tech Stack
- **Python 3.11+**: The programming language used for backend development.
- **Javascript**: Used in dynamic web updates and generating data visualizations.
- **Django**: A high-level web framework that encourages rapid development and clean, pragmatic design.
- **PostgreSQL** (with **pgvector** and **pg_trgm**): SQL database used for relational data, full-text and trigram search, and vector embeddings.
- **Redis**: noSQL key value database used for caching external API responses and user queries.
- **Strawberry GraphQL**: A GraphQL framework used for efficient mobile app requests and personalized feeds.
- **asyncio**: A library for writing concurrent code using the async/await syntax.
- **TensorFlow**: Machine Learning library used to predict bill vote results.
- **Stripe** and **StoreKit 2 (Apple In-App Purchase)**: subscriptions on web, Android and iOS.
- **Web Push / Notifications**: A custom module for managing notifications to users.
- **Docker**: Docker is used to containerize the application and its dependencies, ensuring consistent environments across development and production.

## Key Components
- **`USQuery`**: The Django project root and URL routing configuration.
- **`BillQuery`**: Contains views and templates specifically for bill and vote pages.
- **`SenateQuery`**: Models and helper functions for managing congressional data.
- **`app.utils.py`**: Core utilities for scraping, parsing, and implementing business logic.
- **`notifications`**: Handlers for push notifications and other user alerts.
- **`strawberryAPI`**: Contains schemas, types, and queries for the GraphQL endpoint.

## Testing
A pytest + pytest-django suite under `USQuery/tests/`, split into:
- **`tests/unit/`**: pure logic with no database (ID encoding, parsers, billing rules, tier limits, HTTP retry and single-flight caching).
- **`tests/integration/`**: Django, DRF and GraphQL clients against a real PostgreSQL + pgvector database: auth and OAuth, Stripe webhooks and the subscription API, Apple In-App Purchase, tier gating, notifications, search, and static-file builds. Tests marked `slow` cover the heavier data pipelines.

The suite is hermetic. A dedicated settings module never reads production configuration, a session-level guard aborts the run unless the database is the disposable test container, and every outbound network call is blocked unless a test explicitly mocks it.

```bash
cd USQuery
docker compose up -d test-db              # pgvector/pg17 on localhost:5433
pip install -r requirements-dev.txt
pytest tests/unit                          # no database needed
pytest tests/integration -m "not slow"
pytest                                     # everything
```

## CI/CD
`.github/workflows/tests.yml` runs on every push and pull request:
1. **unit**: the unit suite.
2. **integration**: a migration-drift check, then the integration suite against a pgvector service container, with coverage.
3. **slow**: the pipeline tests (also nightly).
4. **docker-build**: builds the production image.
5. **promote**: when every job passes on `dockerized-app`, fast-forwards `master` to that commit. In the private repository, `master` is the branch the production host deploys from; here it only demonstrates the flow.

No repository secrets are needed: every credential is stubbed in the test settings.

## Contact
For questions or feedback, please open an issue on this repository.
