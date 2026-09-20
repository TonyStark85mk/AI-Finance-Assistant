from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, joblib
from datetime import datetime
from ml_model import predict_category, forecast_next_month, CATEGORIES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.path.join(os.path.dirname(__file__), "finance.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions(
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('income','expense')),
        category TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    CREATE TABLE IF NOT EXISTS budgets(
        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        category TEXT NOT NULL,
        limit_amount REAL NOT NULL,
        UNIQUE(user_id, month, category),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    CREATE TABLE IF NOT EXISTS predictions(
        prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER,
        predicted_category TEXT,
        confidence REAL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS insights(
        insight_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        insight_text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)
    conn.commit()
    conn.close()

def login_required():
    return "user_id" in session

@app.route("/")
def index():
    if login_required():
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))
        try:
            conn = get_db()
            conn.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                         (name,email,generate_password_hash(password),datetime.now().isoformat()))
            conn.commit()
            conn.close()
            flash("Registration successful. Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    uid = session["user_id"]
    conn = get_db()
    income = conn.execute("SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE user_id=? AND type='income'",(uid,)).fetchone()["s"]
    expense = conn.execute("SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE user_id=? AND type='expense'",(uid,)).fetchone()["s"]
    cats = conn.execute("""SELECT COALESCE(category,'Other') category, SUM(amount) total
                           FROM transactions WHERE user_id=? AND type='expense'
                           GROUP BY category ORDER BY total DESC""",(uid,)).fetchall()
    recent = conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC, transaction_id DESC LIMIT 8",(uid,)).fetchall()
    month = datetime.now().strftime("%Y-%m")
    budgets = conn.execute("SELECT * FROM budgets WHERE user_id=? AND month=?",(uid,month)).fetchall()
    conn.close()
    forecast = forecast_next_month(uid)
    insight = make_insight(uid, income, expense, cats, budgets)
    return render_template("dashboard.html", name=session["name"], income=income, expense=expense,
                           balance=income-expense, categories=cats, recent=recent, budgets=budgets,
                           forecast=forecast, insight=insight, month=month)

def make_insight(uid, income, expense, cats, budgets):
    if not cats:
        return "Add a few expenses to receive AI-powered spending insights."
    top = cats[0]["category"]
    top_amt = cats[0]["total"]
    if income > 0 and expense > income:
        return f"Your expenses exceed your recorded income by ₹{expense-income:,.2f}. Review your spending."
    if budgets:
        for b in budgets:
            spent = get_db().execute("""SELECT COALESCE(SUM(amount),0) s FROM transactions
                                        WHERE user_id=? AND type='expense' AND category=? AND substr(date,1,7)=?""",
                                     (uid,b["category"],b["month"])).fetchone()["s"]
            if spent >= b["limit_amount"]:
                return f"Your {b['category']} spending has reached/exceeded the ₹{b['limit_amount']:,.0f} budget."
    return f"Your highest spending category is {top} at ₹{top_amt:,.2f}. Consider reviewing this category."

@app.route("/transactions", methods=["GET","POST"])
def transactions():
    if not login_required(): return redirect(url_for("login"))
    uid = session["user_id"]
    if request.method == "POST":
        date = request.form["date"]
        desc = request.form["description"].strip()
        amount = float(request.form["amount"])
        typ = request.form["type"]
        category = request.form.get("category","").strip()
        if typ == "expense" and not category:
            category, confidence = predict_category(desc)
        elif typ == "income":
            category, confidence = "Income", 1.0
        else:
            confidence = 1.0
        conn = get_db()
        cur = conn.execute("""INSERT INTO transactions(user_id,date,description,amount,type,category)
                              VALUES(?,?,?,?,?,?)""",(uid,date,desc,amount,typ,category))
        tid = cur.lastrowid
        if typ == "expense":
            conn.execute("""INSERT INTO predictions(transaction_id,predicted_category,confidence,created_at)
                            VALUES(?,?,?,?)""",(tid,category,confidence,datetime.now().isoformat()))
        conn.commit(); conn.close()
        flash(f"Transaction added. Category: {category}")
        return redirect(url_for("transactions"))
    conn = get_db()
    rows = conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC, transaction_id DESC",(uid,)).fetchall()
    conn.close()
    return render_template("transactions.html", transactions=rows, categories=CATEGORIES, today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/transactions/delete/<int:tid>", methods=["POST"])
def delete_transaction(tid):
    if not login_required(): return redirect(url_for("login"))
    conn=get_db()
    conn.execute("DELETE FROM transactions WHERE transaction_id=? AND user_id=?",(tid,session["user_id"]))
    conn.commit(); conn.close()
    return redirect(url_for("transactions"))

@app.route("/budgets", methods=["GET","POST"])
def budgets():
    if not login_required(): return redirect(url_for("login"))
    uid=session["user_id"]
    if request.method=="POST":
        month=request.form["month"]; category=request.form["category"]; limit=float(request.form["limit"])
        conn=get_db()
        conn.execute("""INSERT INTO budgets(user_id,month,category,limit_amount) VALUES(?,?,?,?)
                        ON CONFLICT(user_id,month,category) DO UPDATE SET limit_amount=excluded.limit_amount""",
                     (uid,month,category,limit))
        conn.commit(); conn.close()
        flash("Budget saved.")
        return redirect(url_for("budgets"))
    conn=get_db()
    rows=conn.execute("SELECT * FROM budgets WHERE user_id=? ORDER BY month DESC",(uid,)).fetchall()
    conn.close()
    return render_template("budgets.html", budgets=rows, categories=CATEGORIES, month=datetime.now().strftime("%Y-%m"))

@app.route("/predict-category", methods=["POST"])
def api_predict():
    if not login_required(): return jsonify({"error":"Unauthorized"}),401
    data=request.get_json(force=True)
    cat, conf=predict_category(data.get("description",""))
    return jsonify({"category":cat,"confidence":round(conf,3)})

@app.route("/api/chart")
def chart():
    if not login_required(): return jsonify({})
    conn=get_db()
    rows=conn.execute("""SELECT substr(date,1,7) month, type, SUM(amount) total
                         FROM transactions WHERE user_id=? GROUP BY month,type ORDER BY month""",(session["user_id"],)).fetchall()
    conn.close()
    months=sorted(set(r["month"] for r in rows))
    income=[next((r["total"] for r in rows if r["month"]==m and r["type"]=="income"),0) for m in months]
    expense=[next((r["total"] for r in rows if r["month"]==m and r["type"]=="expense"),0) for m in months]
    return jsonify({"months":months,"income":income,"expense":expense})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
