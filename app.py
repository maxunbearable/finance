import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    transactions = db.execute("SELECT symbol, name, SUM(shares) AS shares, price, SUM(total) AS total FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]['cash']
    total = cash
    for transaction in transactions:
        total += transaction['total']
    return render_template("home.html", transactions=transactions, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stockDTO = lookup(request.form.get("symbol"))
        if not symbol or not int(shares) > 0 or stockDTO is None:
            return apology("must provide valid symbol and shares", 403)
        currentUserDTO = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]
        if (stockDTO['price'] * float(shares)) > currentUserDTO['cash']:
            return apology("not enough cash", 403)
        date = datetime.now().strftime("%d/%m/%Y %H:%M:%S");
        db.execute("INSERT INTO transactions (user_id, shares, price, total, symbol, name, time) VALUES (?, ?, ?, ?, ?, ?, ?)", session["user_id"], shares, stockDTO['price'], stockDTO['price'] * float(shares), symbol, stockDTO['name'], date)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", currentUserDTO['cash'] - (stockDTO['price'] * float(shares)), session["user_id"])
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/password", methods=["GET", "POST"])
@login_required
def lpassword():
    """Log user in"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("confirmation"):
            return apology("must provide new password", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)

        # Remember which user has logged in
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(request.form.get("confirmation")), session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("password.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol");
        if not symbol:
            return apology("must provide symbol", 403)
        return render_template("quoted.html", lookup=lookup(symbol))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        existingUser = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if existingUser:
            return apology("user already exists", 403)

        if not (request.form.get("password") == request.form.get("confirmation")):
            return apology("passwords don't match", 403)


        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stockDTO = lookup(request.form.get("symbol"))
        if not symbol or not int(shares) > 0 or stockDTO is None:
            return apology("must provide valid symbol and shares", 403)
        currentShares = db.execute("SELECT SUM(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", session["user_id"], symbol)[0]['shares']
        if (currentShares < int(shares)):
            return apology("too many shares", 403)
        date = datetime.now().strftime("%d/%m/%Y %H:%M:%S");
        currentUserDTO = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]
        db.execute("INSERT INTO transactions (user_id, shares, price, total, symbol, name, time) VALUES (?, ?, ?, ?, ?, ?, ?)", session["user_id"], -int(shares), stockDTO['price'], stockDTO['price'] * float(shares), symbol, stockDTO['name'], date)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", currentUserDTO['cash'] + (stockDTO['price'] * float(shares)), session["user_id"])
        return redirect("/")
    elif request.method == "GET":
        transactions = db.execute("SELECT symbol, name, SUM(shares) AS shares, price, SUM(total) AS total FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", transactions=transactions)
