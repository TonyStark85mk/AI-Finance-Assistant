# AI Finance Assistant

A beginner-friendly academic Major Project based on the supplied SRS.

## Features
- Registration/login with password hashing
- Income and expense CRUD
- ML expense categorization using TF-IDF + Logistic Regression
- Monthly/category budgets
- Dashboard with income, expenses and balance
- Spending charts
- Basic future-spending estimate
- AI-style rule-based financial insights
- SQLite database
- REST-style category prediction endpoint

## Run in VS Code (Windows)

1. Install Python 3.11 or 3.12.
2. Open this folder in VS Code.
3. Create a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

If PowerShell blocks activation, use:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Install packages:
```powershell
python -m pip install -r requirements.txt
```

5. Start:
```powershell
python app.py
```

6. Open:
http://127.0.0.1:5000

## Project mapping to SRS
- Authentication -> /register, /login
- Transaction management -> /transactions
- AI categorization -> ml_model.py + /predict-category
- Budget management -> /budgets
- Dashboard/reports -> /dashboard
- Spending prediction -> forecast_next_month()
- Insights -> make_insight()
- Database -> finance.db (SQLite)

## Important
This is an educational prototype, not professional financial advice. Before submission, add your college/project details, screenshots, test cases, diagrams, and expand the training dataset.
