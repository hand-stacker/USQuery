# USQuery

USQuery is a web application designed to provide users with easy access to congressional data, including bills and votes. This project leverages modern technologies to ensure a robust and efficient experience.

## About this repository

This is a public snapshot of the USQuery backend as of May 2026. Active development continues in a private repository, where new features are being developed alongside proprietary logic I'm not open-sourcing.

## Tech Stack
- **Python 3.11+**: The programming language used for backend development.
- **Javascript**: Used in dynamic web updates and generating data visualizations.
- **Django**: A high-level web framework that encourages rapid development and clean, pragmatic design.
- **PostgreSQL**: SQL database used for relational data.
- **Redis**: noSQL key value database used for caching external API responses and user queries.
- **Strawberry GraphQL**: A graphQL framework used for efficient mobile app requests and personalized feeds.
- **asyncio**: A library for writing concurrent code using the async/await syntax.
- **TensorFlow**: Machine Learning library used to predict bill vote results.
- **Web Push / Notifications**: A custom module for managing notifications to users.
- **Docker**:  Docker is used to containerize the application and its dependencies, ensuring consistent environments across development and production. 
## Key Components
- **`USQuery`**: The Django project root and URL routing configuration.
- **`BillQuery`**: Contains views and templates specifically for bill and vote pages.
- **`SenateQuery`**: Models and helper functions for managing congressional data.
- **`app.utils.py`**: Core utilities for scraping, parsing, and implementing business logic.
- **`notifications`**: Handlers for push notifications and other user alerts.
- **`strawberryAPI`**: Contains schemas, types, and queries for GraphQL endpoint. (You can explore data through https://www.usquery.com/api/v1.0/graphql/)

## My favorite sections
**`BillQuery.models.py`**: Model definitions for bills, votes, and more. Special type manager functions are made that allow for fast database querying.
**`app.utils.py`**: Most of the sophisticated web scraping, data pipelines, and other commonly used utility functions are stored here.
**`StrawberryAPI.graphql.queries.py`**: Personalized bill feeds are built using an algorithm that ranks bills based on a user's favorite subjects. These queries are optimized through prefetching related data, pagination, and caching results.

## Running Background Tasks
The project utilizes `asyncio` for handling asynchronous operations and may include long-running tasks. For production environments, consider using a task queue like Celery with Redis, or schedule commands using cron or systemd timers.

## Contributing
For details on how to contribute to the project, including workflow, branch naming conventions, and pull request requirements, please refer to `CONTRIBUTING.md`.

## Contact
For questions, issues, or feedback, please open an issue on the repository or reach out to the maintainers through the preferred communication channels.
