from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ================= SECRET KEY =================
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

# ================= UPLOAD CONFIG =================
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= EMAIL CONFIG (DISABLED FOR PRODUCTION) =================
app.config["MAIL_SERVER"] = "localhost"
app.config["MAIL_PORT"] = 8025
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = None
app.config["MAIL_PASSWORD"] = None
app.config["MAIL_DEFAULT_SENDER"] = "noreply@onlinestore.com"
app.config["MAIL_SUPPRESS_SEND"] = True  # Important for Render

mail = Mail(app)

# ================= MYSQL CONFIG (FROM ENV VARIABLES) =================
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB")
app.config["MYSQL_PORT"] = int(os.environ.get("MYSQL_PORT", 3306))

mysql = MySQL(app)

# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")

# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        cur.execute(
            "INSERT INTO users(name,email,password,role) VALUES(%s,%s,%s,%s)",
            (name, email, password, role),
        )
        mysql.connection.commit()
        cur.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password),
        )
        user = cur.fetchone()
        cur.close()

        if user:
            session["user_id"] = user[0]
            session["name"] = user[1]
            session["role"] = user[4]
            session.modified = True
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    products = []

    if session["role"] == "seller":
        cur.execute("SELECT * FROM products WHERE seller_id=%s", (session["user_id"],))
        products = cur.fetchall()

    cur.close()
    return render_template("dashboard.html", products=products)

# ============================================================
# ADD PRODUCT
# ============================================================

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        product_name = request.form.get("product_name")
        description = request.form.get("description")
        price = request.form.get("price")
        image = request.files.get("image")

        image_url = None
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(path)
            image_url = f"uploads/{filename}"

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO products(seller_id, product_name, description, price, image) VALUES(%s,%s,%s,%s,%s)",
            (session["user_id"], product_name, description, price, image_url)
        )
        mysql.connection.commit()
        cur.close()

        flash("Product added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_product.html")

# ============================================================
# VIEW PRODUCTS
# ============================================================

@app.route("/products")
def products():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    products_data = cur.fetchall()
    cur.close()

    return render_template("products.html", products=products_data)

# ============================================================
# PLACE ORDER
# ============================================================

@app.route("/place_order/<int:product_id>", methods=["POST"])
def place_order(product_id):
    if "user_id" not in session or session["role"] != "buyer":
        flash("Login as buyer to order.", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO orders(buyer_id, product_id, status) VALUES(%s,%s,'Pending')",
        (session["user_id"], product_id)
    )
    mysql.connection.commit()
    cur.close()

    flash("Order placed successfully!", "success")
    return redirect(url_for("products"))

# ============================================================
# DELETE PRODUCT
# ============================================================

@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized.", "danger")
        return redirect(url_for("dashboard"))

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM products WHERE product_id=%s AND seller_id=%s",
        (product_id, session["user_id"])
    )
    mysql.connection.commit()
    cur.close()

    flash("Product deleted successfully.", "success")
    return redirect(url_for("dashboard"))

# ============================================================
# VIEW ORDERS
# ============================================================

@app.route("/orders")
def view_orders():
    if "user_id" not in session:
        flash("Login required.", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    user_id = session["user_id"]
    role = session["role"]

    if role == "seller":
        cur.execute("""
            SELECT o.order_id, u1.name, p.product_name, u2.name, o.status, o.order_date
            FROM orders o
            JOIN users u1 ON o.buyer_id = u1.user_id
            JOIN products p ON o.product_id = p.product_id
            JOIN users u2 ON p.seller_id = u2.user_id
            WHERE p.seller_id = %s
            ORDER BY o.order_date DESC
        """, (user_id,))
    else:
        cur.execute("""
            SELECT o.order_id, u1.name, p.product_name, u2.name, o.status, o.order_date
            FROM orders o
            JOIN users u1 ON o.buyer_id = u1.user_id
            JOIN products p ON o.product_id = p.product_id
            JOIN users u2 ON p.seller_id = u2.user_id
            WHERE o.buyer_id = %s
            ORDER BY o.order_date DESC
        """, (user_id,))

    orders = cur.fetchall()
    cur.close()

    return render_template("orders.html", orders=orders)

# ============================================================
# IMPORTANT:
# Do NOT add app.run() for Render deployment
# ============================================================