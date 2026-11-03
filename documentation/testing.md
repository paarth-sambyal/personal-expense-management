# Testing Documentation

## Verification record

The project is designed to be verified against MySQL 8. Run the SQL file first, configure `.env`, install `requirements.txt`, then start `python app.py`. This workspace does not include a configured MySQL server or database credentials, so database-backed cases below require the student to run them in their local MySQL setup.

## Manual functional test cases

| ID | Scenario | Expected result |
|---|---|---|
| T01 | Open `/dashboard` while signed out | Redirect to sign-in |
| T02 | Register with valid name, email and password | Account is stored; password column contains a hash |
| T03 | Register again with the same email | Unique constraint prevents duplicate account |
| T04 | Sign in with incorrect password | Error message; no authenticated session |
| T05 | Sign in correctly, then sign out | Dashboard opens; logout clears session |
| T06 | Add, edit, and delete an income entry | History shows the matching updated state |
| T07 | Add, edit, and delete expenses in different categories | Expense history and category report reflect changes |
| T08 | Submit zero or negative amount | Validation/DB CHECK rejects the write |
| T09 | Create overall and category budget for a month | Budget shows spend and remaining amount |
| T10 | Record spending at 80% and above budget | Near-limit and exceeded messages appear |
| T11 | Search history by text, dates and category | Only matching current-user records appear |
| T12 | Sort history by amount and date | Rows follow selected allowlisted order |
| T13 | Download CSV | CSV opens with header and account transactions |
| T14 | User A attempts a URL containing User B's row ID | No other user's row is updated or deleted |
| T15 | Run `CALL sp_monthly_totals(...)` and query `monthly_summary` | Monthly income/expense results are returned |
| T16 | Insert expense using another user's private category | Trigger rejects the insert |

## Suggested database checks

```sql
SELECT user_id,email,password_hash FROM users;
SELECT * FROM monthly_summary ORDER BY month_start DESC;
SHOW INDEX FROM expenses;
SHOW TRIGGERS;
SHOW PROCEDURE STATUS WHERE Db='personal_expense_db';
```

For a real two-account isolation test, create two users and separate transaction records. Sign in as each account and verify the dashboard and history contain only that account's rows.
