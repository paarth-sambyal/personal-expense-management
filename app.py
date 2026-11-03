"""Personal Expense & Budget Management System — Flask entry point."""
import csv
import io
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import check_password_hash, generate_password_hash
import mysql.connector

from database import query

load_dotenv()
app = Flask(__name__)
class AppJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return DefaultJSONProvider.default(value)

app.json = AppJSONProvider(app)
if os.getenv("RENDER") and not os.getenv("FLASK_SECRET_KEY"):
    raise RuntimeError("Set FLASK_SECRET_KEY in the Render environment before starting the service.")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-secret")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")))


@app.context_processor
def template_dates():
    return {"today": date.today().isoformat(), "current_month": date.today().strftime("%Y-%m"), "now_date": datetime.now().strftime("%A, %d %B")}


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def safe_db(fn):
    """Convert expected database setup/connection errors into a useful message."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except mysql.connector.Error:
            app.logger.exception("Database operation failed")
            return render_template("error.html", code=503, message="Database unavailable. Check MySQL and your .env settings."), 503
    return wrapped


def valid_amount(value):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("999999999.99"):
            raise InvalidOperation
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Enter an amount greater than zero (up to 999,999,999.99).")


@app.template_filter("money")
def money(value):
    return f"₹{float(value or 0):,.2f}"


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))


@app.get("/health")
def health():
    """Render health check; intentionally does not depend on database availability."""
    return jsonify(status="ok"), 200


@app.route("/register", methods=["GET", "POST"])
@safe_db
def register():
    if request.method == "POST":
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not name or len(name) > 100 or "@" not in email or len(email) > 190 or len(password) < 8:
            flash("Enter a name, valid email and password with at least 8 characters.", "danger")
            return render_template("register.html")
        query("INSERT INTO users (full_name, email, password_hash) VALUES (%s,%s,%s)", (name, email, generate_password_hash(password)), commit=True)
        flash("Account created. You can now sign in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@safe_db
def login():
    if request.method == "POST":
        user = query("SELECT user_id, full_name, email, password_hash FROM users WHERE email=%s", (request.form.get("email", "").strip().lower(),), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=user["user_id"], user_name=user["full_name"])
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
@safe_db
def dashboard():
    uid = session["user_id"]
    totals = query("""SELECT COALESCE((SELECT SUM(amount) FROM income WHERE user_id=%s),0) total_income,
        COALESCE((SELECT SUM(amount) FROM expenses WHERE user_id=%s),0) total_expenses,
        COALESCE((SELECT SUM(amount) FROM income WHERE user_id=%s AND DATE_FORMAT(income_date,'%%Y-%%m')=DATE_FORMAT(CURDATE(),'%%Y-%%m')),0) month_income,
        COALESCE((SELECT SUM(amount) FROM expenses WHERE user_id=%s AND DATE_FORMAT(expense_date,'%%Y-%%m')=DATE_FORMAT(CURDATE(),'%%Y-%%m')),0) month_expenses""", (uid, uid, uid, uid), one=True)
    recent = query("""SELECT * FROM (SELECT income_id id, 'Income' kind, source title, amount, income_date txn_date FROM income WHERE user_id=%s
        UNION ALL SELECT expense_id, 'Expense', c.category_name, amount, expense_date FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE user_id=%s) t
        ORDER BY txn_date DESC, id DESC LIMIT 8""", (uid, uid))
    monthly = query("""SELECT m.month_label, COALESCE(i.total,0) income, COALESCE(e.total,0) expenses FROM
        (SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL n MONTH),'%%Y-%%m') ym, DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL n MONTH),'%%b') month_label FROM
        (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5) nums) m
        LEFT JOIN (SELECT DATE_FORMAT(income_date,'%%Y-%%m') ym, SUM(amount) total FROM income WHERE user_id=%s GROUP BY ym) i ON i.ym=m.ym
        LEFT JOIN (SELECT DATE_FORMAT(expense_date,'%%Y-%%m') ym, SUM(amount) total FROM expenses WHERE user_id=%s GROUP BY ym) e ON e.ym=m.ym ORDER BY m.ym""", (uid, uid))
    categories = query("SELECT c.category_name, SUM(e.amount) total FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE e.user_id=%s AND e.expense_date >= DATE_FORMAT(CURDATE(),'%%Y-%%m-01') GROUP BY c.category_id,c.category_name ORDER BY total DESC", (uid,))
    return render_template("dashboard.html", totals=totals, recent=recent, monthly=monthly, categories=categories)


@app.route("/income", methods=["GET", "POST"])
@login_required
@safe_db
def income():
    uid = session["user_id"]
    if request.method == "POST":
        try:
            source = request.form.get("source", "").strip()
            if not source or len(source) > 100: raise ValueError("Income source is required (100 characters max).")
            query("INSERT INTO income (user_id,source,amount,income_date,description) VALUES (%s,%s,%s,%s,%s)", (uid, source, valid_amount(request.form.get("amount")), request.form.get("date") or date.today(), request.form.get("description", "").strip()), commit=True)
            flash("Income added.", "success")
        except ValueError as exc: flash(str(exc), "danger")
        return redirect(url_for("income"))
    rows = query("SELECT * FROM income WHERE user_id=%s ORDER BY income_date DESC,income_id DESC", (uid,))
    return render_template("income.html", rows=rows)


@app.route("/income/<int:item_id>/edit", methods=["POST"])
@login_required
@safe_db
def edit_income(item_id):
    try:
        source = request.form.get("source", "").strip()
        if not source or len(source) > 100: raise ValueError("Income source is required.")
        query("UPDATE income SET source=%s,amount=%s,income_date=%s,description=%s WHERE income_id=%s AND user_id=%s", (source, valid_amount(request.form.get("amount")), request.form.get("date"), request.form.get("description", "").strip(), item_id, session["user_id"]), commit=True)
        flash("Income updated.", "success")
    except ValueError as exc: flash(str(exc), "danger")
    return redirect(url_for("income"))


@app.post("/income/<int:item_id>/delete")
@login_required
@safe_db
def delete_income(item_id):
    query("DELETE FROM income WHERE income_id=%s AND user_id=%s", (item_id, session["user_id"]), commit=True)
    flash("Income deleted.", "success")
    return redirect(url_for("income"))


def expense_form_data(uid):
    return query("SELECT category_id,category_name FROM categories WHERE user_id IS NULL OR user_id=%s ORDER BY category_name", (uid,))


@app.route("/expenses", methods=["GET", "POST"])
@login_required
@safe_db
def expenses():
    uid = session["user_id"]
    cats = expense_form_data(uid)
    if request.method == "POST":
        try:
            query("INSERT INTO expenses (user_id,category_id,amount,expense_date,description) SELECT %s,category_id,%s,%s,%s FROM categories WHERE category_id=%s AND (user_id IS NULL OR user_id=%s)", (uid, valid_amount(request.form.get("amount")), request.form.get("date") or date.today(), request.form.get("description", "").strip(), request.form.get("category_id"), uid), commit=True)
            flash("Expense added.", "success")
        except ValueError as exc: flash(str(exc), "danger")
        return redirect(url_for("expenses"))
    rows = query("SELECT e.*,c.category_name FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE e.user_id=%s ORDER BY e.expense_date DESC,e.expense_id DESC", (uid,))
    return render_template("expenses.html", rows=rows, categories=cats)


@app.route("/expenses/<int:item_id>/edit", methods=["POST"])
@login_required
@safe_db
def edit_expense(item_id):
    try:
        query("UPDATE expenses e JOIN categories c ON c.category_id=%s AND (c.user_id IS NULL OR c.user_id=%s) SET e.category_id=c.category_id,e.amount=%s,e.expense_date=%s,e.description=%s WHERE e.expense_id=%s AND e.user_id=%s", (request.form.get("category_id"), session["user_id"], valid_amount(request.form.get("amount")), request.form.get("date"), request.form.get("description", "").strip(), item_id, session["user_id"]), commit=True)
        flash("Expense updated.", "success")
    except ValueError as exc: flash(str(exc), "danger")
    return redirect(url_for("expenses"))


@app.post("/expenses/<int:item_id>/delete")
@login_required
@safe_db
def delete_expense(item_id):
    query("DELETE FROM expenses WHERE expense_id=%s AND user_id=%s", (item_id, session["user_id"]), commit=True)
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses"))


@app.route("/budgets", methods=["GET", "POST"])
@login_required
@safe_db
def budgets():
    uid = session["user_id"]
    cats = expense_form_data(uid)
    if request.method == "POST":
        try:
            amount = valid_amount(request.form.get("amount"))
            month = request.form.get("month")
            category_id = request.form.get("category_id") or None
            if not month or len(month) != 7: raise ValueError("Choose a budget month.")
            if category_id:
                query("INSERT INTO budgets (user_id,category_id,budget_month,amount) SELECT %s,category_id,%s,%s FROM categories WHERE category_id=%s AND (user_id IS NULL OR user_id=%s) ON DUPLICATE KEY UPDATE amount=VALUES(amount)", (uid, month + "-01", amount, category_id, uid), commit=True)
            else:
                query("INSERT INTO budgets (user_id,category_id,budget_month,amount) VALUES (%s,NULL,%s,%s) ON DUPLICATE KEY UPDATE amount=VALUES(amount)", (uid, month + "-01", amount), commit=True)
            flash("Budget saved.", "success")
        except ValueError as exc: flash(str(exc), "danger")
        return redirect(url_for("budgets"))
    rows = query("""SELECT b.budget_id,b.budget_month,b.amount,c.category_name,COALESCE(SUM(e.amount),0) spent
        FROM budgets b LEFT JOIN categories c ON c.category_id=b.category_id LEFT JOIN expenses e ON e.user_id=b.user_id
        AND e.expense_date >= b.budget_month AND e.expense_date < DATE_ADD(b.budget_month,INTERVAL 1 MONTH)
        AND (b.category_id IS NULL OR e.category_id=b.category_id) WHERE b.user_id=%s
        GROUP BY b.budget_id,b.budget_month,b.amount,c.category_name ORDER BY b.budget_month DESC,b.budget_id", (uid,))
    return render_template("budgets.html", rows=rows, categories=cats)


@app.post("/budgets/<int:budget_id>/delete")
@login_required
@safe_db
def delete_budget(budget_id):
    query("DELETE FROM budgets WHERE budget_id=%s AND user_id=%s", (budget_id, session["user_id"]), commit=True)
    flash("Budget deleted.", "success")
    return redirect(url_for("budgets"))


@app.route("/transactions")
@login_required
@safe_db
def transactions():
    uid = session["user_id"]
    search = request.args.get("q", "").strip()
    start, end, category = request.args.get("start", ""), request.args.get("end", ""), request.args.get("category", "")
    sort = request.args.get("sort", "date_desc")
    order = {"date_asc": "txn_date ASC", "amount_asc": "amount ASC", "amount_desc": "amount DESC", "date_desc": "txn_date DESC"}.get(sort, "txn_date DESC")
    # UNION creates one consistent history; dynamic SQL is limited to a fixed allowlist above.
    rows = query(f"""SELECT * FROM (SELECT income_id id,'Income' kind,source title,amount,income_date txn_date,description,NULL category_id FROM income WHERE user_id=%s
        UNION ALL SELECT e.expense_id,'Expense',c.category_name,e.amount,e.expense_date,e.description,e.category_id FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE e.user_id=%s) t
        WHERE (%s='' OR title LIKE CONCAT('%%',%s,'%%') OR COALESCE(description,'') LIKE CONCAT('%%',%s,'%%'))
        AND (%s='' OR txn_date >= %s) AND (%s='' OR txn_date <= %s) AND (%s='' OR category_id=%s OR (kind='Income' AND %s='income')) ORDER BY {order},id DESC""",
        (uid,uid,search,search,search,start,start,end,end,category,category,category))
    categories = expense_form_data(uid)
    return render_template("transactions.html", rows=rows, categories=categories, filters=request.args)


@app.route("/reports")
@login_required
@safe_db
def reports():
    uid = session["user_id"]
    monthly = query("SELECT DATE_FORMAT(month_start,'%%Y-%%m') month,COALESCE(i.total,0) income,COALESCE(e.total,0) expenses FROM monthly_summary WHERE user_id=%s ORDER BY month_start DESC LIMIT 12", (uid,))
    categories = query("SELECT c.category_name,SUM(e.amount) total FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE e.user_id=%s GROUP BY c.category_id,c.category_name ORDER BY total DESC", (uid,))
    budgets = query("SELECT DATE_FORMAT(b.budget_month,'%%Y-%%m') month,COALESCE(c.category_name,'Overall') category,b.amount budget,COALESCE(SUM(e.amount),0) spent FROM budgets b LEFT JOIN categories c ON c.category_id=b.category_id LEFT JOIN expenses e ON e.user_id=b.user_id AND e.expense_date>=b.budget_month AND e.expense_date<DATE_ADD(b.budget_month,INTERVAL 1 MONTH) AND (b.category_id IS NULL OR e.category_id=b.category_id) WHERE b.user_id=%s GROUP BY b.budget_id,c.category_name ORDER BY b.budget_month DESC LIMIT 12", (uid,))
    return render_template("reports.html", monthly=monthly, categories=categories, budgets=budgets)


@app.route("/reports.csv")
@login_required
@safe_db
def export_csv():
    uid = session["user_id"]
    rows = query("SELECT * FROM (SELECT 'Income' type,source category,amount,income_date txn_date,description FROM income WHERE user_id=%s UNION ALL SELECT 'Expense',c.category_name,e.amount,e.expense_date,e.description FROM expenses e JOIN categories c ON c.category_id=e.category_id WHERE e.user_id=%s) t ORDER BY txn_date DESC", (uid,uid))
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Type", "Source / Category", "Amount", "Date", "Description"])
    for row in rows: writer.writerow([row["type"],row["category"],row["amount"],row["txn_date"],row["description"]])
    return Response("\ufeff" + stream.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=expense_report.csv"})


@app.errorhandler(404)
def not_found(_): return render_template("error.html", code=404, message="We could not find that page."), 404


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
