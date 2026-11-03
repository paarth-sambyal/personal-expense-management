# Deploy Pocketwise on Render

This project is configured as a Render Python web service. Render runs Flask through Gunicorn, checks `/health`, and generates a secret key when the Blueprint is created. The MySQL database is hosted separately; `render.yaml` asks for its connection values without saving credentials in the repository.

## 1. Create the MySQL database

Provision a MySQL 8 database with a managed MySQL host that allows connections from Render. Keep the database hostname, port, database name, username, password and (if provided) CA certificate. Choose a provider/region with reliable external connectivity. For a course demo, a managed provider such as Aiven or Railway can host MySQL; check its current plan limits and connection/TLS instructions before provisioning.

Run `database/expense_management.sql` once against that database using the provider's SQL console or a local MySQL client. It creates the schema, default categories, indexes, view, trigger and stored procedure. Do not run the schema against an existing production database without first reviewing its DDL.

## 2. Put this project in a Git repository

Push the contents of `Personal_Expense_Management/` to the root of a GitHub repository. The root should contain `render.yaml`, `app.py`, and `requirements.txt` together. Do not commit `.env` or paste database credentials into source files.

## 3. Create the Render service

1. In Render, choose **New → Blueprint** and connect the repository.
2. Render reads `render.yaml` and creates the web service. It generates `FLASK_SECRET_KEY` and prompts for the values marked `sync: false`.
3. Enter the MySQL host, port, username and password from the database provider. If the provider gives a CA certificate file, make it available to the service as a secret file and set `DB_SSL_CA` to its mounted path. Leave `DB_SSL_CA` empty if the provider does not require a CA file; TLS may still be negotiated by Connector/Python when the server supports it.
4. Confirm the service settings: build command `pip install -r requirements.txt`, start command `gunicorn app:app`, health check path `/health`.
5. Deploy and wait for the health check to pass. Visit the generated `onrender.com` URL and register a test account.

Alternatively, create a Python web service manually with those same commands and set `FLASK_SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and optional `DB_SSL_CA` in the service's Environment page.

## 4. Verify the deployed app

- `/health` should return `{"status":"ok"}`.
- Register, log in, add income and an expense, set a budget, then verify dashboard totals and reports.
- Download the CSV and verify it contains only the signed-in account's entries.
- Inspect Render logs for database or TLS connection errors. Confirm the database provider permits inbound connections from the deployed web service.

## Operations and limits

- `render.yaml` uses Render's free web-service plan to keep the demo setup low-cost. Free services may spin down when idle and take time to wake; check current Render pricing/limits before relying on it for a live presentation.
- Keep the database on a persistent managed database plan. Do not use an ephemeral local file/database for financial records.
- Set `FLASK_DEBUG=0` in production. The app refuses to start on Render if `FLASK_SECRET_KEY` is missing and marks session cookies secure on Render.
- Back up the MySQL database before schema changes. The provided SQL is an initial schema script, not an automated migration tool.
