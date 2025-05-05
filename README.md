# KaydangPT Backend

This directory contains the Django backend application for KaydangPT, providing an API to query a knowledge base built from indexed documents. It uses Sentence Transformers for embeddings, pgvector for similarity search, Django Q2 for background processing, and integrates with a Generative AI service (like Gemini) for answer generation.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python** (3.9+ recommended)
*   **Pip** (Python package installer)
*   **PostgreSQL** (13+ recommended) with the **pgvector** extension enabled. (Django Q2 will use this for its broker by default)
*   **Git**

## Configuration

Configuration is managed via environment variables. Create a `.env` file in this `backend` directory.

1.  **Copy the example:** `cp .env.example .env` (You might need to create `.env.example` first if it doesn't exist).
2.  **Edit `.env`** with your specific settings.

```dotenv
# .env example content

# Django Settings
SECRET_KEY='your_strong_random_secret_key' # CHANGE THIS! Use a secure random generator
DEBUG=True # Set to False in production!
ALLOWED_HOSTS='127.0.0.1,localhost' # Add your domain(s) in production

# Database (PostgreSQL with pgvector)
# Django Q2 will use this database as its default broker
# Example: postgresql://user:password@host:port/database_name
DATABASE_URL='postgresql://kaydangpt_user:your_db_password@localhost:5432/kaydangpt_db'

# Generative AI Service (e.g., Gemini)
GEMINI_API_KEY='your_gemini_api_key'

# Embedding Model (Should match model used in tasks.py)
# Optional: Override the default model name if needed
# EMBEDDING_MODEL_NAME='all-MiniLM-L6-v2'

# Django Q2 Settings (Defaults often suffice)
# See Django Q2 documentation for more options if needed
# Q_CLUSTER = {
#     'name': 'kaydangpt_q',
#     'workers': 4,  # Adjust based on server resources
#     'timeout': 90,
#     'retry': 120,
#     'queue_limit': 50,
#     'bulk': 10,
#     'orm': 'default'  # Uses the default Django database connection
# }

# Other settings
# CORS_ALLOWED_ORIGINS='http://localhost:3000,http://127.0.0.1:3000' # Example for frontend development

```

**Important:**

*   **`SECRET_KEY`**: Must be kept secret and unique for production.
*   **`DEBUG`**: Must be `False` in production.
*   **`ALLOWED_HOSTS`**: Must include the domain(s) or IP addresses your application is served from in production.
*   Ensure the PostgreSQL database specified in `DATABASE_URL` exists, the user has permissions, and the `pgvector` extension is created (`CREATE EXTENSION IF NOT EXISTS vector;` in the database). Django Q2 will automatically create its necessary tables during migration.

## Running Locally (Development)

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\\Scripts\\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # (Make sure requirements.txt exists and includes django-q2)
    ```
4.  **Set up the database:**
    Ensure the PostgreSQL service is running.
    Create the `pgvector` extension in your PostgreSQL database if you haven't already.
    ```bash
    psql -d your_database_name -c "CREATE EXTENSION IF NOT EXISTS vector;"
    ```
5.  **Apply database migrations:** (This will also create tables needed by Django Q2)
    ```bash
    python manage.py migrate
    ```
6.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```
    The API should be available at `http://127.0.0.1:8000/`.

7.  **Run Django Q2 Cluster (for background tasks):**
    Open *another* terminal, activate the virtual environment (`source venv/bin/activate`), and run:
    ```bash
    python manage.py qcluster
    ```
    This command starts the background worker process that will pick up tasks like document processing.

## Deployment

Deploying this application involves several components:

1.  **Web Server (WSGI):** Use Gunicorn or uWSGI to run the Django application.
2.  **Reverse Proxy:** Use Nginx or Apache to handle incoming HTTP requests, serve static files, and potentially manage SSL.
3.  **Database:** A production-ready PostgreSQL instance with the `pgvector` extension enabled. Django Q2 will use this database for task queuing.
4.  **Django Q2 Cluster Process:** Run the `python manage.py qcluster` command using a process manager like `systemd` or `supervisor` to ensure it runs reliably in the background.
5.  **Static Files:** Run `python manage.py collectstatic` and configure your reverse proxy (Nginx) to serve the collected static files.
6.  **Environment Variables:** Securely provide the environment variables to the application processes (do not commit `.env` to Git in production).
7.  **Model Cache:** Ensure the Sentence Transformer model can be downloaded and cached persistently. This might involve configuring a specific cache directory and potentially mounting a volume in containerized environments.

## Deployment with Dokploy

Dokploy simplifies deployment using containerization. Here's a general approach:

1.  **Create a `Dockerfile`:** Define how to build the Docker image for your Django application.

    ```dockerfile
    # Dockerfile example (in backend directory)
    FROM python:3.10-slim

    WORKDIR /app

    # Set environment variables to prevent buffering issues
    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1

    # Install system dependencies if needed (e.g., for psycopg2)
    # RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

    # Install Python dependencies
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy application code
    COPY . .

    # Expose the port Gunicorn will run on
    EXPOSE 8000

    # Collect static files (optional, can be done in entrypoint or separate build step)
    # RUN python manage.py collectstatic --noinput

    # Command to run the application using Gunicorn (for the 'web' service)
    # Replace 'kaydangpt.wsgi:application' with your actual WSGI application path
    # The CMD will be overridden for the qcluster service.
    CMD ["gunicorn", "--bind", "0.0.0.0:8000", "kaydangpt.wsgi:application"]
    ```

2.  **Define Services in Dokploy (using `docker-compose.yml` principles):**
    Dokploy typically uses a `docker-compose.yml` structure or its own UI to define services. You'll need services for:
    *   **`db` (PostgreSQL with pgvector):**
        *   Use an image like `ankane/pgvector` or `pgvector/pgvector`.
        *   Define persistent volume for data (`/var/lib/postgresql/data`).
        *   Set PostgreSQL environment variables (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`). Remember Django Q2 uses this DB too.
    *   **`web` (Django/Gunicorn):**
        *   Build from your `Dockerfile`.
        *   Mount or copy code volume.
        *   Link environment variables (from Dokploy secrets or `.env` file).
        *   Depends on `db`.
        *   Map port `8000`.
        *   Define a volume for the Sentence Transformer model cache (e.g., map `/root/.cache` or a custom path inside the container to a persistent Dokploy volume) to avoid re-downloading.
    *   **`qcluster` (Django Q2 Worker):**
        *   Build from the same `Dockerfile` as `web`.
        *   **Override the command** to run the Django Q2 cluster: `python manage.py qcluster`
        *   Link environment variables.
        *   Depends on `db`.
        *   Mount the same model cache volume as `web`.
    *   **`nginx` (Optional - Reverse Proxy):**
        *   Use the standard `nginx:alpine` image.
        *   Configure Nginx to proxy requests to the `web` service (port 8000).
        *   Configure serving static files (requires a volume shared with the `web` service after `collectstatic` runs, or a multi-stage Docker build).
        *   Map ports `80` and/or `443`.

3.  **Configure in Dokploy UI:**
    *   Create a new application in Dokploy.
    *   Point it to your Git repository (if using Git integration) or specify the Docker image/compose setup.
    *   Define necessary **Environment Variables** securely within Dokploy for each service (`DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, `ALLOWED_HOSTS`, `DEBUG=False`, etc.). Note that `DATABASE_URL` is used by both `web` and `qcluster`.
    *   Set up **Persistent Volumes** for PostgreSQL data and the Sentence Transformer model cache.
    *   Configure **Networking** and **Ports**.
    *   Deploy the application.

**Dokploy Specific Notes:**

*   Consult the Dokploy documentation for specifics on defining services, volumes, and environment variables.
*   Pay close attention to volume mounting for the **model cache**. You want the model downloaded once and shared between `web` and `qcluster` services if possible, and persisted across deployments. You might need to configure the cache directory used by `sentence-transformers` via environment variables if the default (`~/.cache/huggingface/`) is not suitable within the container.
*   Ensure `collectstatic` is handled correctly in your Docker/Dokploy workflow. Either run it during the image build or in an entrypoint script before Gunicorn starts, ensuring the static files are placed where Nginx (if used) can access them via a shared volume.
*   Make sure `python manage.py migrate` is run as part of your deployment process (often in an entrypoint script or init container) before starting the `web` or `qcluster` services, especially on the first deployment, to set up Django Q2's tables. 