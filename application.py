import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM shares_owned WHERE owned_by = :id", id=session["user_id"])
    cash_left = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    holdings = 0
    for row in rows:
        holdings += row["holding"]

    holdings = round(holdings, 2)
    cash_left = round(cash_left[0]["cash"], 2)
    return render_template("index.html", rows=rows, total_h=holdings, cash_left=cash_left)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))

        if not symbol or symbol == None:
            return apology("Symbol not found", 403)
        if not request.form.get("shares"):
            return apology("Enter number o shares", 403)

        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

        if float(rows[0]["cash"]) < (int(request.form.get("shares")) * float(symbol["price"])):
            return apology("Not enough cash", 403)
        else:
            cash = float(rows[0]["cash"]) - (int(request.form.get("shares")) * float(symbol["price"]))
            total = int(request.form.get("shares")) * float(symbol["price"])

            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash, id=session["user_id"])
            db.execute("INSERT INTO orders (order_by, share_name, shares_qty, share_price, purchase_total) VALUES (:by, :name, :qty, :price, :total)",
                        by=session["user_id"], name=symbol["symbol"], qty=int(request.form.get("shares")), price=symbol["price"], total=total)

            # Handles index
            shares_owned_rows = db.execute("SELECT owned_by, share_name, shares_qty FROM shares_owned WHERE owned_by = :id", id=session["user_id"])

            # Make a list of share_name that are attached to the user
            share_name_list = []
            for row in shares_owned_rows:
                share_name_list.append(row["share_name"])

            if symbol["symbol"] in share_name_list:
                for row in shares_owned_rows:
                    if row["share_name"] == symbol["symbol"]:
                        new_qty = int(row["shares_qty"] + int(request.form.get("shares")));
                        db.execute("UPDATE shares_owned SET shares_qty =:qty , holding =:hold WHERE share_name =:name",
                                    qty=new_qty ,hold=float(new_qty * float(symbol["price"])), name=symbol["symbol"])

            else:
                db.execute("INSERT INTO shares_owned (owned_by, share_name, shares_qty, share_price, holding) VALUES (:by, :name, :qty, :price, :hold)",
                            by=session["user_id"], name=symbol["symbol"], qty=int(request.form.get("shares")), price=symbol["price"], hold=total)

            return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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

        if not request.form.get("symbol") or lookup(request.form.get("symbol")) == None:
            return apology("Symbol not found", 403)

        symbol = lookup(request.form.get("symbol"))
        return render_template("quoted.html", symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Ensure Username was provided
        if not request.form.get("username"):
            return apology("Username must be provided", 403)

        # Ensure Password was provided
        elif not request.form.get("password"):
            return apology("Password must be provided", 403)

        # Ensure password confimation was provided
        elif not request.form.get("confirmation"):
            return apology("Password confirmation must be provided", 403)

        # Verify if the username is not in the database
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        if len(rows) == 1:
            return apology("Username is taken", 403)



        if request.form.get("password") == request.form.get("confirmation"):

            passw = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
                        username=request.form.get("username"), password=passw)
            return redirect("/login")
        else:
            return apology("Passwords do not match", 403)


    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
