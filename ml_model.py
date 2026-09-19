import os, re, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

CATEGORIES = ["Food","Transport","Shopping","Bills","Entertainment","Health","Education","Other"]

# Small educational seed dataset. Add more rows in dataset/transactions.csv for better accuracy.
DATA = [
("swiggy dinner","Food"),("zomato lunch","Food"),("restaurant meal","Food"),("groceries","Food"),
("milk bread vegetables","Food"),("pizza","Food"),("uber ride","Transport"),("ola cab","Transport"),
("bus ticket","Transport"),("metro recharge","Transport"),("petrol","Transport"),("fuel","Transport"),
("amazon order","Shopping"),("clothes","Shopping"),("shoes","Shopping"),("flipkart purchase","Shopping"),
("electricity bill","Bills"),("water bill","Bills"),("internet bill","Bills"),("mobile recharge","Bills"),
("netflix","Entertainment"),("movie ticket","Entertainment"),("concert","Entertainment"),
("medicine","Health"),("doctor consultation","Health"),("pharmacy","Health"),
("college fee","Education"),("books","Education"),("course fee","Education"),
("rent","Bills"),("insurance premium","Bills"),("gift","Other"),("miscellaneous","Other")
]

_model=None
def train_model():
    global _model
    x=[a for a,b in DATA]; y=[b for a,b in DATA]
    vec=TfidfVectorizer(ngram_range=(1,2), lowercase=True)
    X=vec.fit_transform(x)
    clf=LogisticRegression(max_iter=1000)
    clf.fit(X,y)
    _model=(vec,clf)

def predict_category(text):
    global _model
    if _model is None: train_model()
    text=(text or "").strip().lower()
    if not text: return "Other",0.0
    vec,clf=_model
    p=clf.predict_proba(vec.transform([text]))[0]
    i=p.argmax()
    return clf.classes_[i], float(p[i])

def forecast_next_month(user_id):
    import sqlite3, os
    db=os.path.join(os.path.dirname(__file__),"finance.db")
    if not os.path.exists(db): return 0
    conn=sqlite3.connect(db)
    rows=conn.execute("""SELECT substr(date,1,7) m, SUM(amount) total
                         FROM transactions WHERE user_id=? AND type='expense'
                         GROUP BY m ORDER BY m""",(user_id,)).fetchall()
    conn.close()
    vals=[r[1] for r in rows]
    if not vals: return 0
    if len(vals)==1: return round(vals[0],2)
    # Simple moving average, suitable as a transparent fresher-level baseline.
    return round(sum(vals[-3:])/min(3,len(vals)),2)
