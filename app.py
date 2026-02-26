from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- UPLOAD CONFIG ----------------
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- EMAIL CONFIG (Console Mode) ----------------
app.config["MAIL_SERVER"] = "localhost"
app.config["MAIL_PORT"] = 8025
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = None
app.config["MAIL_PASSWORD"] = None
app.config["MAIL_DEFAULT_SENDER"] = "noreply@onlinestore.com"
app.config["MAIL_SUPPRESS_SEND"] = False

mail = Mail(app)

# ---------------- MYSQL CONFIG ----------------
app.config["MYSQL_HOST"] = "127.0.0.1"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "savio"
app.config["MYSQL_DB"] = "online_store"

mysql = MySQL(app)

# ============================================================
# ROOT
# ============================================================

@app.route("/")
def index():
    return render_template('index.html')

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
            flash("Email already registered. Please use another email.", "danger")
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
            flash("Invalid credentials, please try again.", "danger")
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
        flash("Please login to access the dashboard", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    products = []

    if session["role"] == "seller":
        cur.execute(
            "SELECT * FROM products WHERE seller_id=%s",
            (session["user_id"],)
        )
        products = cur.fetchall()

    cur.close()
    return render_template("dashboard.html", products=products)

# ============================================================
# ADD PRODUCT
# ============================================================

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized access", "danger")
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
# GET ALL PRODUCTS
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
        flash("You must be logged in as a buyer to order.", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO orders(buyer_id, product_id, status) VALUES(%s,%s,'Pending')",
        (session["user_id"], product_id)
    )
    mysql.connection.commit()
    
    # Send email
    cur.execute('''
        SELECT u.email, u.name, p.product_name 
        FROM products p 
        JOIN users u ON p.seller_id = u.user_id 
        WHERE p.product_id = %s
    ''', (product_id,))
    seller_info = cur.fetchone()
    cur.close()

    if seller_info:
        seller_email, seller_name, product_name = seller_info
        try:
            msg = Message(
                subject='New Order Received!',
                recipients=[seller_email],
                body=f"Hello {seller_name},\n\nYou have received a new order for '{product_name}'.\nPlease check your dashboard for more details.\n\nThank you,\nOnline Store Team"
            )
            mail.send(msg)
            print("=====================================================")
            print(f"EMAIL SENT TO: {seller_email}")
            print(f"SUBJECT: New Order Received!")
            print(f"BODY:\n{msg.body}")
            print("=====================================================")
        except Exception as e:
            print(f"Failed to send email: {e}")

    flash("Order placed successfully!", "success")
    return redirect(url_for("products"))

# ============================================================
# EDIT PRODUCT
# ============================================================

@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))

    cur = mysql.connection.cursor()
    
    if request.method == "POST":
        product_name = request.form.get("product_name")
        description = request.form.get("description")
        price = request.form.get("price")
        image = request.files.get("image")
        
        cur.execute("SELECT image FROM products WHERE product_id=%s AND seller_id=%s", (product_id, session["user_id"]))
        product = cur.fetchone()
        
        if not product:
            cur.close()
            flash("Unauthorized access!", "danger")
            return redirect(url_for("dashboard"))
            
        old_image_url = product[0]
        image_url = old_image_url
        
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(path)
            image_url = f"uploads/{filename}"

        cur.execute(
            "UPDATE products SET product_name=%s, description=%s, price=%s, image=%s WHERE product_id=%s",
            (product_name, description, price, image_url, product_id)
        )
        mysql.connection.commit()
        cur.close()

        flash("Product updated successfully", "success")
        return redirect(url_for("dashboard"))

    cur.execute("SELECT * FROM products WHERE product_id=%s AND seller_id=%s", (product_id, session["user_id"]))
    product = cur.fetchone()
    cur.close()
    
    if not product:
        flash("Product not found or unauthorized", "danger")
        return redirect(url_for("dashboard"))

    return render_template("edit_product.html", product=product)

# ============================================================
# DELETE PRODUCT
# ============================================================

@app.route("/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "user_id" not in session or session["role"] != "seller":
        flash("Unauthorized", "danger")
        return redirect(url_for("dashboard"))

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM products WHERE product_id=%s AND seller_id=%s",
        (product_id, session["user_id"])
    )
    mysql.connection.commit()
    cur.close()

    flash("Product deleted successfully", "success")
    return redirect(url_for("dashboard"))

# ============================================================
# VIEW ORDERS
# ============================================================

@app.route("/orders")
def view_orders():
    if "user_id" not in session:
        flash("Please login to view orders", "warning")
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    user_id = session["user_id"]
    role = session["role"]

    if role == "seller":
        query = """
        SELECT 
            o.order_id,
            u1.name AS buyer_name,
            p.product_name,
            u2.name AS seller_name,
            o.status,
            o.order_date
        FROM orders o
        JOIN users u1 ON o.buyer_id = u1.user_id
        JOIN products p ON o.product_id = p.product_id
        JOIN users u2 ON p.seller_id = u2.user_id
        WHERE p.seller_id = %s
        ORDER BY o.order_date DESC;
        """
        cur.execute(query, (user_id,))
    else:
        query = """
        SELECT 
            o.order_id,
            u1.name AS buyer_name,
            p.product_name,
            u2.name AS seller_name,
            o.status,
            o.order_date
        FROM orders o
        JOIN users u1 ON o.buyer_id = u1.user_id
        JOIN products p ON o.product_id = p.product_id
        JOIN users u2 ON p.seller_id = u2.user_id
        WHERE o.buyer_id = %s
        ORDER BY o.order_date DESC;
        """
        cur.execute(query, (user_id,))

    orders = cur.fetchall()
    cur.close()

    return render_template("orders.html", orders=orders)


if __name__ == "__main__":
    app.run(debug=True)