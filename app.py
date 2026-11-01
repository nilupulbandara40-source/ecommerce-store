
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
import sqlite3
import os
import math
import re
from contextlib import closing

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "novacart-demo-secret-key-change-before-deployment"
)


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():
    with closing(db()) as con:

        con.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price REAL NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                image_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                email TEXT NOT NULL,
                address TEXT NOT NULL,
                total REAL NOT NULL CHECK(total >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL
                    REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER
                    REFERENCES products(id) ON DELETE SET NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0)
            );
        """)

        count = con.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

        if count == 0:
            products = [
                (
                    "Wireless Headphones",
                    "Electronics",
                    "Comfortable wireless headphones for everyday listening.",
                    8500,
                    12,
                    ""
                ),
                (
                    "Classic Backpack",
                    "Accessories",
                    "A durable backpack for study, work and travel.",
                    4200,
                    18,
                    ""
                ),
                (
                    "Smart Watch",
                    "Electronics",
                    "A simple smart watch with activity tracking features.",
                    12500,
                    7,
                    ""
                ),
                (
                    "Ceramic Mug",
                    "Home",
                    "Reusable ceramic mug for hot and cold drinks.",
                    950,
                    30,
                    ""
                )
            ]

            con.executemany("""
                INSERT INTO products
                (name, category, description, price, stock, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, products)

        con.commit()


# --------------------------------------------------
# PRODUCT HELPER
# --------------------------------------------------

def get_product(product_id):
    with closing(db()) as con:
        return con.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()


# --------------------------------------------------
# CART COUNT
# --------------------------------------------------

@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    return {
        "cart_count": sum(cart.values())
    }


# --------------------------------------------------
# HOME PAGE / PRODUCT SEARCH / FILTER / SORT
# --------------------------------------------------

@app.route("/")
def index():

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")

    allowed_sort = {
        "price_asc": "price ASC",
        "price_desc": "price DESC",
        "name": "name COLLATE NOCASE ASC",
        "newest": "id DESC"
    }

    sql = "SELECT * FROM products WHERE stock >= 0"
    params = []

    if search:
        sql += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """
        params.extend([f"%{search}%"] * 3)

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY " + allowed_sort.get(sort, "id DESC")

    with closing(db()) as con:

        products = con.execute(
            sql, params
        ).fetchall()

        categories = [
            row["category"]
            for row in con.execute(
                "SELECT DISTINCT category FROM products ORDER BY category"
            ).fetchall()
        ]

    return render_template(
        "index.html",
        products=products,
        categories=categories,
        q=search,
        selected_category=category,
        sort=sort
    )


# --------------------------------------------------
# PRODUCT DETAILS
# --------------------------------------------------

@app.route("/product/<int:product_id>")
def product_detail(product_id):

    product = get_product(product_id)

    if not product:
        abort(404)

    return render_template(
        "detail.html",
        product=product
    )


# --------------------------------------------------
# ADD PRODUCT TO CART
# --------------------------------------------------

@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    product = get_product(product_id)

    if not product:
        abort(404)

    try:
        quantity = int(request.form.get("quantity", "1"))
    except (ValueError, TypeError):
        quantity = 0

    if quantity < 1:
        flash("Quantity must be at least 1.", "error")

    elif quantity > product["stock"]:
        flash(
            "Requested quantity exceeds available stock.",
            "error"
        )

    else:
        cart = session.get("cart", {})
        key = str(product_id)

        new_quantity = int(cart.get(key, 0)) + quantity

        if new_quantity > product["stock"]:
            flash(
                "Cart quantity exceeds available stock.",
                "error"
            )
        else:
            cart[key] = new_quantity
            session["cart"] = cart

            flash(
                "Product added to your cart.",
                "success"
            )

    return redirect(request.referrer or url_for("index"))


# --------------------------------------------------
# VIEW SHOPPING CART
# --------------------------------------------------

@app.route("/cart")
def cart():

    cart_data = session.get("cart", {})
    items = []
    total = 0

    with closing(db()) as con:

        for product_id, quantity in cart_data.items():

            product = con.execute(
                "SELECT * FROM products WHERE id = ?",
                (int(product_id),)
            ).fetchone()

            if product:
                subtotal = product["price"] * quantity

                items.append({
                    "product": product,
                    "quantity": quantity,
                    "subtotal": subtotal
                })

                total += subtotal

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# --------------------------------------------------
# UPDATE CART QUANTITIES
# --------------------------------------------------

@app.route("/cart/update", methods=["POST"])
def update_cart():

    cart_data = session.get("cart", {})

    with closing(db()) as con:

        for product_id in list(cart_data.keys()):

            field = "qty_" + product_id

            if field not in request.form:
                continue

            try:
                quantity = int(request.form[field])
            except (ValueError, TypeError):
                quantity = 0

            product = con.execute(
                "SELECT stock FROM products WHERE id = ?",
                (int(product_id),)
            ).fetchone()

            if quantity <= 0:
                cart_data.pop(product_id, None)

            elif product and quantity <= product["stock"]:
                cart_data[product_id] = quantity

            else:
                flash(
                    "Quantity exceeds available stock.",
                    "error"
                )

    session["cart"] = cart_data

    return redirect(url_for("cart"))


# --------------------------------------------------
# CHECKOUT
# --------------------------------------------------

@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    cart_data = session.get("cart", {})

    if not cart_data:
        flash("Your cart is empty.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":

        name = request.form.get(
            "customer_name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        address = request.form.get(
            "address", ""
        ).strip()

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        if (
            not name
            or len(name) > 100
            or not re.fullmatch(email_pattern, email)
            or len(email) > 150
            or not address
            or len(address) > 500
        ):
            flash(
                "Please enter valid customer information.",
                "error"
            )
            return redirect(url_for("checkout"))

        with closing(db()) as con:

            try:
                line_items = []
                total = 0

                # Check stock before placing the order
                for product_id, quantity in cart_data.items():

                    product = con.execute(
                        "SELECT * FROM products WHERE id = ?",
                        (int(product_id),)
                    ).fetchone()

                    if (
                        not product
                        or quantity < 1
                        or quantity > product["stock"]
                    ):
                        raise ValueError(
                            "Stock changed. Please review your cart."
                        )

                    line_items.append(
                        (product, quantity)
                    )

                    total += product["price"] * quantity

                # Create order
                cursor = con.execute("""
                    INSERT INTO orders
                    (customer_name, email, address, total)
                    VALUES (?, ?, ?, ?)
                """, (
                    name,
                    email,
                    address,
                    total
                ))

                order_id = cursor.lastrowid

                # Save order items and reduce stock
                for product, quantity in line_items:

                    con.execute("""
                        INSERT INTO order_items
                        (
                            order_id,
                            product_id,
                            product_name,
                            quantity,
                            unit_price
                        )
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        order_id,
                        product["id"],
                        product["name"],
                        quantity,
                        product["price"]
                    ))

                    con.execute("""
                        UPDATE products
                        SET stock = stock - ?
                        WHERE id = ?
                    """, (
                        quantity,
                        product["id"]
                    ))

                con.commit()

            except (ValueError, sqlite3.Error) as exc:

                con.rollback()

                if isinstance(exc, ValueError):
                    flash(str(exc), "error")
                else:
                    flash(
                        "Could not place order. Please try again.",
                        "error"
                    )

                return redirect(url_for("cart"))

        session["cart"] = {}

        return render_template(
            "success.html",
            order_id=order_id,
            total=total
        )

    return render_template("checkout.html")


# --------------------------------------------------
# ADMIN - VIEW PRODUCTS
# --------------------------------------------------

@app.route("/admin/products")
def admin_products():

    with closing(db()) as con:

        products = con.execute("""
            SELECT *
            FROM products
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "admin.html",
        products=products
    )


# --------------------------------------------------
# PRODUCT VALIDATION
# --------------------------------------------------

def validate_product(form):

    name = form.get("name", "").strip()
    category = form.get("category", "").strip()
    description = form.get("description", "").strip()
    image_url = form.get("image_url", "").strip()

    errors = []

    # Validate price
    try:
        price = float(form.get("price", ""))

        if not math.isfinite(price) or price < 0:
            errors.append(
                "Price must be a valid non-negative number."
            )

    except (ValueError, TypeError):
        price = 0
        errors.append("Please enter a valid price.")

    # Validate stock
    try:
        stock = int(form.get("stock", ""))

        if stock < 0:
            errors.append(
                "Stock must be a non-negative whole number."
            )

    except (ValueError, TypeError):
        stock = 0
        errors.append("Please enter a valid stock quantity.")

    # Validate name
    if not name:
        errors.append("Product name is required.")

    elif len(name) > 100:
        errors.append(
            "Product name must not exceed 100 characters."
        )

    # Validate category
    if not category:
        errors.append("Category is required.")

    elif len(category) > 50:
        errors.append(
            "Category must not exceed 50 characters."
        )

    # Validate description
    if len(description) > 1000:
        errors.append(
            "Description must not exceed 1000 characters."
        )

    # Validate image URL
    if image_url and not re.match(
        r"^https?://",
        image_url,
        re.IGNORECASE
    ):
        errors.append(
            "Image URL must start with http:// or https://."
        )

    data = {
        "name": name,
        "category": category,
        "description": description,
        "price": price,
        "stock": stock,
        "image_url": image_url
    }

    return data, errors


# --------------------------------------------------
# CREATE PRODUCT
# --------------------------------------------------

@app.route("/admin/products/new", methods=["GET", "POST"])
def product_new():

    if request.method == "POST":

        data, errors = validate_product(request.form)

        if errors:

            for error in errors:
                flash(error, "error")

            return render_template(
                "product_form.html",
                product=data,
                heading="Add product",
                action=url_for("product_new")
            )

        with closing(db()) as con:

            con.execute("""
                INSERT INTO products
                (
                    name,
                    category,
                    description,
                    price,
                    stock,
                    image_url
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["name"],
                data["category"],
                data["description"],
                data["price"],
                data["stock"],
                data["image_url"]
            ))

            con.commit()

        flash(
            "Product created successfully.",
            "success"
        )

        return redirect(url_for("admin_products"))

    return render_template(
        "product_form.html",
        product={},
        heading="Add product",
        action=url_for("product_new")
    )


# --------------------------------------------------
# UPDATE PRODUCT
# --------------------------------------------------

@app.route(
    "/admin/products/<int:product_id>/edit",
    methods=["GET", "POST"]
)
def product_edit(product_id):

    product = get_product(product_id)

    if not product:
        abort(404)

    if request.method == "POST":

        data, errors = validate_product(request.form)

        if errors:

            for error in errors:
                flash(error, "error")

            data["id"] = product_id

            return render_template(
                "product_form.html",
                product=data,
                heading="Edit product",
                action=url_for(
                    "product_edit",
                    product_id=product_id
                )
            )

        with closing(db()) as con:

            con.execute("""
                UPDATE products
                SET
                    name = ?,
                    category = ?,
                    description = ?,
                    price = ?,
                    stock = ?,
                    image_url = ?
                WHERE id = ?
            """, (
                data["name"],
                data["category"],
                data["description"],
                data["price"],
                data["stock"],
                data["image_url"],
                product_id
            ))

            con.commit()

        flash(
            "Product updated successfully.",
            "success"
        )

        return redirect(url_for("admin_products"))

    return render_template(
        "product_form.html",
        product=product,
        heading="Edit product",
        action=url_for(
            "product_edit",
            product_id=product_id
        )
    )


# --------------------------------------------------
# DELETE PRODUCT
# --------------------------------------------------

@app.route(
    "/admin/products/<int:product_id>/delete",
    methods=["POST"]
)
def product_delete(product_id):

    with closing(db()) as con:

        product = con.execute(
            "SELECT id FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if not product:
            abort(404)

        con.execute(
            "DELETE FROM products WHERE id = ?",
            (product_id,)
        )

        con.commit()

    flash(
        "Product deleted successfully.",
        "success"
    )

    return redirect(url_for("admin_products"))


# --------------------------------------------------
# ADMIN - VIEW ALL ORDERS
# --------------------------------------------------

@app.route("/admin/orders")
def admin_orders():

    with closing(db()) as con:

        orders = con.execute("""
            SELECT *
            FROM orders
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "orders.html",
        orders=orders
    )


# --------------------------------------------------
# ORDER DETAILS
# --------------------------------------------------

@app.route("/admin/orders/<int:order_id>")
def order_detail(order_id):

    with closing(db()) as con:

        order = con.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not order:
            abort(404)

        items = con.execute(
            "SELECT * FROM order_items WHERE order_id = ?",
            (order_id,)
        ).fetchall()

    return render_template(
        "order_detail.html",
        order=order,
        items=items
    )


# --------------------------------------------------
# 404 ERROR PAGE
# --------------------------------------------------

@app.errorhandler(404)
def not_found(error):

    return render_template("404.html"), 404


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    init_db()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
