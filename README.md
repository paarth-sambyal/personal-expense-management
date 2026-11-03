# Personal Expense & Budget Management System

A Flask and MySQL application for tracking income, expenses, monthly budgets and reports. It uses server-rendered HTML, responsive CSS, Chart.js and parameterised MySQL queries. Each data query is scoped to the signed-in user's ID.

## Requirements and setup

- Python 3.10 or newer
- MySQL 8.0 or newer

1. Create a MySQL account for the application, or use an existing local account.
2. Run `database/expense_management.sql` in MySQL Workbench or the MySQL command-line client. It creates `personal_expense_db`, the tables, indexes, default categories, view, procedure and triggers.
3. Create and activate a virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set `DB_USER`, `DB_PASSWORD`, and a long random `FLASK_SECRET_KEY`. The `.env` file is ignored by Git.
5. Start the server with `python app.py`, then visit `http://127.0.0.1:5000` and register an account.

Do not expose Flask's development server to the public internet. For deployment, set `FLASK_DEBUG=0`, use HTTPS, and serve Flask through a production WSGI server.

## Features

- Registration, password hashing, login/logout and session-based access control.
- Dashboard totals, current-month savings, recent transactions, six-month cash flow and monthly category breakdown.
- Income and expense create/read/update/delete workflows.
- Overall and category budgets, spend tracking, remaining amount and 80%/100% alerts.
- Search, date filters, category filter and allowlisted sorting for transaction history.
- Monthly and category reports plus a downloadable CSV of account transactions.

## Project map

- `app.py` — routes, validation, access checks, reporting and CSV generation.
- `database.py` — pooled MySQL connection and transaction helpers.
- `database/expense_management.sql` — schema and DBMS examples.
- `templates/` — server-rendered pages and forms.
- `static/css/style.css` — responsive dashboard design.
- `static/js/script.js` — edit dialogs, delete confirmations and charts.
- `documentation/academic_report.md` — abstract, schema, ER model, normalisation and SQL explanations.
- `documentation/testing.md` — manual test plan and verification record.
- `render.yaml` and `DEPLOY_RENDER.md` — Render Blueprint and deployment walkthrough.

## Notes

The SQL uses MySQL 8 features including CHECK constraints, generated columns and window-free aggregate views. If you use an older MySQL release, upgrade it rather than removing constraints. A user can only query, edit, or delete rows that include their own `user_id` predicate; category ownership is checked by the database triggers as well as the application.
