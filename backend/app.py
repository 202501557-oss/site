
from flask import Flask, jsonify, send_from_directory, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import csv
import os
import sqlite3
import uuid


app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "white-black-secret-key-change-this")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# ==========================================
# PATHS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "users.db"
)

FRONTEND_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "frontend")
)

STYLE_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "style")
)

PRODUCTS_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "products")
)

PRODUCTS_FILE = os.path.join(
    PRODUCTS_DIR,
    "products.csv"
)

PRODUCT_IMAGES_DIR = os.path.join(
    PRODUCTS_DIR,
    "images"
)


# ==========================================
# ADMIN
# ==========================================

ADMIN_EMAIL = "hossam57hatem2007@gmail.com"


def is_admin():
    return (
        session.get("admin_authenticated") is True
        and
        session.get("user_email", "").lower()
        == ADMIN_EMAIL.lower()
    )


# ==========================================
# DATABASE
# ==========================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():

    connection = get_db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, product_id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


init_database()


# ==========================================
# PRODUCTS
# ==========================================

def get_products():

    products = []

    if not os.path.exists(PRODUCTS_FILE):
        return products

    with open(
        PRODUCTS_FILE,
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            try:

                product = {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "price": float(row["price"]),
                    "category": row["category"],
                    "image": row["image"]
                }

                # Optional description support
                if "description" in row:
                    product["description"] = row.get(
                        "description",
                        ""
                    ) or ""
                else:
                    product["description"] = ""

                products.append(product)

            except (
                KeyError,
                ValueError
            ):
                continue

    return products


def get_product_by_id(product_id):

    try:
        product_id = int(product_id)
    except (
        ValueError,
        TypeError
    ):
        return None

    products = get_products()

    for product in products:

        if product["id"] == product_id:
            return product

    return None


# ==========================================
# SAVE PRODUCTS
# ==========================================

def save_products(products):

    os.makedirs(
        PRODUCTS_DIR,
        exist_ok=True
    )

    # Support description while keeping old CSV files working
    fieldnames = [
        "id",
        "name",
        "price",
        "category",
        "image",
        "description"
    ]

    with open(
        PRODUCTS_FILE,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for product in products:

            writer.writerow({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "category": product["category"],
                "image": product["image"],
                "description": product.get(
                    "description",
                    ""
                )
            })


# ==========================================
# ADD PRODUCT
# ==========================================

def add_product(
    name,
    price,
    category,
    image,
    description=""
):

    products = get_products()

    if products:

        new_id = max(
            product["id"]
            for product in products
        ) + 1

    else:

        new_id = 1

    product = {
        "id": new_id,
        "name": name,
        "price": price,
        "category": category,
        "image": image,
        "description": description
    }

    products.append(product)

    save_products(products)

    return product


# ==========================================
# UPDATE PRODUCT
# ==========================================

def update_product(
    product_id,
    name,
    price,
    category,
    image=None,
    description=None
):

    products = get_products()

    updated_product = None

    for product in products:

        if product["id"] == product_id:

            product["name"] = name
            product["price"] = price
            product["category"] = category

            if image:
                product["image"] = image

            if description is not None:
                product["description"] = description

            updated_product = product

            break

    if not updated_product:
        return None

    save_products(products)

    return updated_product


# ==========================================
# DELETE PRODUCT
# ==========================================

def delete_product(product_id):

    products = get_products()

    product_to_delete = None

    for product in products:

        if product["id"] == product_id:

            product_to_delete = product
            break

    if not product_to_delete:
        return None

    remaining_products = [
        product
        for product in products
        if product["id"] != product_id
    ]

    save_products(
        remaining_products
    )

    return product_to_delete


# ==========================================
# IMAGE UPLOAD
# ==========================================

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif"
}


def allowed_image(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[-1]
        .lower()
    )

    return extension in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file):

    if not file:
        return None

    if not file.filename:
        return None

    if not allowed_image(file.filename):
        return None

    os.makedirs(
        PRODUCT_IMAGES_DIR,
        exist_ok=True
    )

    original_name = secure_filename(
        file.filename
    )

    if not original_name:
        return None

    extension = (
        original_name
        .rsplit(".", 1)[-1]
        .lower()
    )

    unique_name = (
        f"{uuid.uuid4().hex}.{extension}"
    )

    file_path = os.path.join(
        PRODUCT_IMAGES_DIR,
        unique_name
    )

    file.save(file_path)

    return unique_name


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    if "user_id" not in session:

        return send_from_directory(
            FRONTEND_DIR,
            "auth.html"
        )

    return send_from_directory(
        FRONTEND_DIR,
        "index.html"
    )


# ==========================================
# AUTH PAGE
# ==========================================

@app.route("/auth")
def auth():

    return send_from_directory(
        FRONTEND_DIR,
        "auth.html"
    )


# ==========================================
# ADMIN LOGIN PAGE
# ==========================================

@app.route("/admin")
def admin():

    # Always require Admin Login when entering /admin
    session.pop(
        "admin_authenticated",
        None
    )

    return send_from_directory(
        FRONTEND_DIR,
        "admin-login.html"
    )


# ==========================================
# ADMIN DASHBOARD PAGE
# ==========================================

@app.route("/admin/dashboard")
def admin_dashboard_page():

    if not is_admin():

        return send_from_directory(
            FRONTEND_DIR,
            "admin-login.html"
        )

    return send_from_directory(
        FRONTEND_DIR,
        "admin.html"
    )


# ==========================================
# PRODUCT DETAILS PAGE
# ==========================================

@app.route("/product/<int:product_id>")
def product_details_page(product_id):

    if "user_id" not in session:

        return redirect("/auth")

    return send_from_directory(
        FRONTEND_DIR,
        "product-details.html"
    )


# ==========================================
# STATIC FILES
# ==========================================

@app.route("/style/<path:filename>")
def style_files(filename):

    return send_from_directory(
        STYLE_DIR,
        filename
    )


@app.route("/images/<path:filename>")
def product_images(filename):

    return send_from_directory(
        PRODUCT_IMAGES_DIR,
        filename
    )


# ==========================================
# SIGN UP
# ==========================================

@app.route(
    "/api/auth/signup",
    methods=["POST"]
)
def signup():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    name = data.get(
        "name",
        ""
    ).strip()

    email = data.get(
        "email",
        ""
    ).strip().lower()

    password = data.get(
        "password",
        ""
    )

    if not name or not email or not password:

        return jsonify({
            "success": False,
            "message": "All fields are required"
        }), 400

    if len(password) < 6:

        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters"
        }), 400

    connection = get_db()

    existing_user = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if existing_user:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Email already exists"
        }), 409

    password_hash = generate_password_hash(
        password
    )

    cursor = connection.execute(
        """
        INSERT INTO users (
            name,
            email,
            password
        )
        VALUES (?, ?, ?)
        """,
        (
            name,
            email,
            password_hash
        )
    )

    connection.commit()

    user_id = cursor.lastrowid

    connection.close()

    session["user_id"] = user_id
    session["user_name"] = name
    session["user_email"] = email

    session.pop(
        "admin_authenticated",
        None
    )

    return jsonify({
        "success": True,
        "message": "Account created successfully"
    })


# ==========================================
# NORMAL LOGIN
# ==========================================

@app.route(
    "/api/auth/login",
    methods=["POST"]
)
def login():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    email = data.get(
        "email",
        ""
    ).strip().lower()

    password = data.get(
        "password",
        ""
    )

    connection = get_db()

    user = connection.execute(
        """
        SELECT id, name, email, password
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    connection.close()

    if not user:

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    # Normal login NEVER authenticates Admin
    session.pop(
        "admin_authenticated",
        None
    )

    return jsonify({
        "success": True,
        "message": "Login successful"
    })


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route(
    "/api/admin/login",
    methods=["POST"]
)
def admin_login():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    email = data.get(
        "email",
        ""
    ).strip().lower()

    password = data.get(
        "password",
        ""
    )

    if email != ADMIN_EMAIL.lower():

        return jsonify({
            "success": False,
            "message": "Admin access denied"
        }), 403

    connection = get_db()

    user = connection.execute(
        """
        SELECT id, name, email, password
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    connection.close()

    if not user:

        return jsonify({
            "success": False,
            "message": "Admin account not found"
        }), 404

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "success": False,
            "message": "Invalid admin email or password"
        }), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    session["admin_authenticated"] = True

    return jsonify({
        "success": True,
        "message": "Admin login successful"
    })


# ==========================================
# ADMIN LOGOUT
# ==========================================

@app.route(
    "/api/admin/logout",
    methods=["POST"]
)
def admin_logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Admin logged out successfully"
    })


# ==========================================
# CURRENT USER
# ==========================================

@app.route(
    "/api/auth/me",
    methods=["GET"]
)
def current_user():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Not logged in"
        }), 401

    return jsonify({
        "success": True,
        "id": session["user_id"],
        "name": session["user_name"],
        "email": session["user_email"],
        "is_admin": is_admin()
    })


# ==========================================
# NORMAL LOGOUT
# ==========================================

@app.route(
    "/api/auth/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


# ==========================================
# GET PRODUCTS
# SEARCH + FILTER
# ==========================================

@app.route(
    "/api/products",
    methods=["GET"]
)
def products_api():

    products = get_products()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    category = request.args.get(
        "category",
        ""
    ).strip().lower()

    min_price = request.args.get(
        "min_price"
    )

    max_price = request.args.get(
        "max_price"
    )

    if search:

        products = [
            product
            for product in products
            if (
                search in product["name"].lower()
                or search in product["category"].lower()
                or search in product.get(
                    "description",
                    ""
                ).lower()
            )
        ]

    if category and category != "all":

        products = [
            product
            for product in products
            if product["category"].lower()
            == category
        ]

    if min_price:

        try:

            min_value = float(min_price)

            products = [
                product
                for product in products
                if product["price"] >= min_value
            ]

        except ValueError:
            pass

    if max_price:

        try:

            max_value = float(max_price)

            products = [
                product
                for product in products
                if product["price"] <= max_value
            ]

        except ValueError:
            pass

    return jsonify(products)


# ==========================================
# GET PRODUCT DETAILS
# ==========================================

@app.route(
    "/api/products/<int:product_id>",
    methods=["GET"]
)
def product_details_api(product_id):

    product = get_product_by_id(
        product_id
    )

    if not product:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    return jsonify({
        "success": True,
        "product": product
    })


# ==========================================
# GET CATEGORIES
# ==========================================

@app.route(
    "/api/categories",
    methods=["GET"]
)
def categories_api():

    products = get_products()

    categories = sorted(
        {
            product["category"]
            for product in products
            if product["category"]
        }
    )

    return jsonify({
        "success": True,
        "categories": categories
    })


# ==========================================
# ADD PRODUCT
# ==========================================

@app.route(
    "/api/products",
    methods=["POST"]
)
def add_product_api():

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    # ======================================
    # IMAGE UPLOAD FORM
    # ======================================

    if request.files:

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        price_value = request.form.get(
            "price",
            ""
        ).strip()

        image_file = request.files.get(
            "image"
        )

        try:

            price = float(
                price_value
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                "success": False,
                "message": "Invalid price"
            }), 400

        if (
            not name
            or not category
            or not image_file
            or price < 0
        ):

            return jsonify({
                "success": False,
                "message": "Please fill all fields correctly"
            }), 400

        image_name = save_uploaded_image(
            image_file
        )

        if not image_name:

            return jsonify({
                "success": False,
                "message": "Invalid image file"
            }), 400

        product = add_product(
            name,
            price,
            category,
            image_name,
            description
        )

        return jsonify({
            "success": True,
            "message": "Product added successfully",
            "product": product
        })


    # ======================================
    # JSON PRODUCT
    # ======================================

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    name = data.get(
        "name",
        ""
    ).strip()

    category = data.get(
        "category",
        ""
    ).strip()

    image = data.get(
        "image",
        ""
    ).strip()

    description = data.get(
        "description",
        ""
    ).strip()

    try:

        price = float(
            data.get(
                "price",
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid price"
        }), 400

    if (
        not name
        or not category
        or not image
        or price < 0
    ):

        return jsonify({
            "success": False,
            "message": "Please fill all fields correctly"
        }), 400

    product = add_product(
        name,
        price,
        category,
        image,
        description
    )

    return jsonify({
        "success": True,
        "message": "Product added successfully",
        "product": product
    })


# ==========================================
# EDIT PRODUCT
# ==========================================

@app.route(
    "/api/products/<int:product_id>",
    methods=["PUT"]
)
def edit_product_api(product_id):

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    existing_product = get_product_by_id(
        product_id
    )

    if not existing_product:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    # ======================================
    # FORM DATA / IMAGE
    # ======================================

    if request.form:

        name = request.form.get(
            "name",
            existing_product["name"]
        ).strip()

        category = request.form.get(
            "category",
            existing_product["category"]
        ).strip()

        description = request.form.get(
            "description",
            existing_product.get(
                "description",
                ""
            )
        ).strip()

        price_value = request.form.get(
            "price",
            existing_product["price"]
        )

        image_file = request.files.get(
            "image"
        )

        try:

            price = float(
                price_value
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                "success": False,
                "message": "Invalid price"
            }), 400

        if (
            not name
            or not category
            or price < 0
        ):

            return jsonify({
                "success": False,
                "message": "Please fill all fields correctly"
            }), 400

        image_name = None

        if image_file and image_file.filename:

            image_name = save_uploaded_image(
                image_file
            )

            if not image_name:

                return jsonify({
                    "success": False,
                    "message": "Invalid image file"
                }), 400

        product = update_product(
            product_id,
            name,
            price,
            category,
            image_name,
            description
        )

        return jsonify({
            "success": True,
            "message": "Product updated successfully",
            "product": product
        })


    # ======================================
    # JSON UPDATE
    # ======================================

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    name = data.get(
        "name",
        existing_product["name"]
    ).strip()

    category = data.get(
        "category",
        existing_product["category"]
    ).strip()

    image = data.get(
        "image",
        existing_product["image"]
    ).strip()

    description = data.get(
        "description",
        existing_product.get(
            "description",
            ""
        )
    ).strip()

    try:

        price = float(
            data.get(
                "price",
                existing_product["price"]
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid price"
        }), 400

    if (
        not name
        or not category
        or price < 0
    ):

        return jsonify({
            "success": False,
            "message": "Please fill all fields correctly"
        }), 400

    product = update_product(
        product_id,
        name,
        price,
        category,
        image,
        description
    )

    return jsonify({
        "success": True,
        "message": "Product updated successfully",
        "product": product
    })


# ==========================================
# DELETE PRODUCT
# ==========================================

@app.route(
    "/api/products/<int:product_id>",
    methods=["DELETE"]
)
def delete_product_api(product_id):

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    product = delete_product(
        product_id
    )

    if not product:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    connection = get_db()

    # Remove deleted product from carts
    connection.execute(
        """
        DELETE FROM cart
        WHERE product_id = ?
        """,
        (product_id,)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Product deleted successfully",
        "product": product
    })


# ==========================================
# ADD TO CART
# ==========================================

@app.route(
    "/api/cart",
    methods=["POST"]
)
def add_to_cart():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    data = request.get_json(silent=True)

    if not data or "product_id" not in data:

        return jsonify({
            "success": False,
            "message": "Product ID is required"
        }), 400

    try:

        product_id = int(
            data["product_id"]
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid product ID"
        }), 400

    product = get_product_by_id(
        product_id
    )

    if not product:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    connection = get_db()

    item = connection.execute(
        """
        SELECT id, quantity
        FROM cart
        WHERE user_id = ?
        AND product_id = ?
        """,
        (
            session["user_id"],
            product_id
        )
    ).fetchone()

    if item:

        connection.execute(
            """
            UPDATE cart
            SET quantity = quantity + 1
            WHERE id = ?
            """,
            (item["id"],)
        )

    else:

        connection.execute(
            """
            INSERT INTO cart (
                user_id,
                product_id,
                quantity
            )
            VALUES (?, ?, ?)
            """,
            (
                session["user_id"],
                product_id,
                1
            )
        )

    connection.commit()

    connection.close()

    return jsonify({
        "success": True,
        "message": "Product added to cart"
    })


# ==========================================
# GET CART
# ==========================================

@app.route(
    "/api/cart",
    methods=["GET"]
)
def get_cart():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    connection = get_db()

    rows = connection.execute(
        """
        SELECT product_id, quantity
        FROM cart
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    items = []

    total = 0

    for row in rows:

        product = get_product_by_id(
            row["product_id"]
        )

        if product:

            quantity = max(
                1,
                int(row["quantity"])
            )

            item_total = (
                product["price"]
                * quantity
            )

            items.append({
                "product": product,
                "quantity": quantity,
                "item_total": round(
                    item_total,
                    2
                )
            })

            total += item_total

    return jsonify({
        "success": True,
        "items": items,
        "total": round(
            total,
            2
        )
    })


# ==========================================
# UPDATE CART QUANTITY
# ==========================================

@app.route(
    "/api/cart/<int:product_id>",
    methods=["PUT"]
)
def update_cart_quantity(product_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    product = get_product_by_id(
        product_id
    )

    if not product:

        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    data = request.get_json(silent=True)

    if not data or "quantity" not in data:

        return jsonify({
            "success": False,
            "message": "Quantity is required"
        }), 400

    try:

        quantity = int(
            data["quantity"]
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid quantity"
        }), 400

    # Quantity 0 means remove item
    if quantity <= 0:

        connection = get_db()

        connection.execute(
            """
            DELETE FROM cart
            WHERE user_id = ?
            AND product_id = ?
            """,
            (
                session["user_id"],
                product_id
            )
        )

        connection.commit()
        connection.close()

        return jsonify({
            "success": True,
            "message": "Product removed from cart"
        })

    # Safety limit
    if quantity > 99:

        quantity = 99

    connection = get_db()

    item = connection.execute(
        """
        SELECT id
        FROM cart
        WHERE user_id = ?
        AND product_id = ?
        """,
        (
            session["user_id"],
            product_id
        )
    ).fetchone()

    if not item:

        connection.execute(
            """
            INSERT INTO cart (
                user_id,
                product_id,
                quantity
            )
            VALUES (?, ?, ?)
            """,
            (
                session["user_id"],
                product_id,
                quantity
            )
        )

    else:

        connection.execute(
            """
            UPDATE cart
            SET quantity = ?
            WHERE user_id = ?
            AND product_id = ?
            """,
            (
                quantity,
                session["user_id"],
                product_id
            )
        )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Cart quantity updated",
        "product_id": product_id,
        "quantity": quantity
    })


# ==========================================
# REMOVE FROM CART
# ==========================================

@app.route(
    "/api/cart/<int:product_id>",
    methods=["DELETE"]
)
def remove_from_cart(product_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    connection = get_db()

    connection.execute(
        """
        DELETE FROM cart
        WHERE user_id = ?
        AND product_id = ?
        """,
        (
            session["user_id"],
            product_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Product removed from cart"
    })


# ==========================================
# CHECKOUT
# ==========================================

@app.route(
    "/api/orders/checkout",
    methods=["POST"]
)
def checkout():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    connection = get_db()

    cart_rows = connection.execute(
        """
        SELECT product_id, quantity
        FROM cart
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchall()

    if not cart_rows:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Your cart is empty"
        }), 400

    order_items = []

    total = 0

    for row in cart_rows:

        product = get_product_by_id(
            row["product_id"]
        )

        if not product:
            continue

        try:
            quantity = int(
                row["quantity"]
            )
        except (
            ValueError,
            TypeError
        ):
            continue

        if quantity <= 0:
            continue

        price = float(
            product["price"]
        )

        total += (
            price * quantity
        )

        order_items.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "price": price,
            "quantity": quantity
        })

    if not order_items:

        connection.close()

        return jsonify({
            "success": False,
            "message": "No valid products in cart"
        }), 400

    total = round(
        total,
        2
    )

    cursor = connection.execute(
        """
        INSERT INTO orders (
            user_id,
            total,
            status
        )
        VALUES (?, ?, ?)
        """,
        (
            session["user_id"],
            total,
            "Pending"
        )
    )

    order_id = cursor.lastrowid

    for item in order_items:

        connection.execute(
            """
            INSERT INTO order_items (
                order_id,
                product_id,
                product_name,
                price,
                quantity
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order_id,
                item["product_id"],
                item["product_name"],
                item["price"],
                item["quantity"]
            )
        )

    connection.execute(
        """
        DELETE FROM cart
        WHERE user_id = ?
        """,
        (session["user_id"],)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Order created successfully",
        "order_id": order_id,
        "total": total,
        "status": "Pending"
    })


# ==========================================
# USER ORDERS
# ==========================================

@app.route(
    "/api/orders",
    methods=["GET"]
)
def user_orders():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    connection = get_db()

    orders = connection.execute(
        """
        SELECT
            id,
            total,
            status,
            created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    result = []

    for order in orders:

        items = connection.execute(
            """
            SELECT
                product_id,
                product_name,
                price,
                quantity
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order["id"],)
        ).fetchall()

        result.append({
            "id": order["id"],
            "total": float(
                order["total"]
            ),
            "status": order["status"],
            "created_at": order["created_at"],
            "items": [
                dict(item)
                for item in items
            ]
        })

    connection.close()

    return jsonify({
        "success": True,
        "orders": result
    })


# ==========================================
# USER ORDER DETAILS
# ==========================================

@app.route(
    "/api/orders/<int:order_id>",
    methods=["GET"]
)
def user_order_details(order_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    connection = get_db()

    order = connection.execute(
        """
        SELECT
            id,
            total,
            status,
            created_at
        FROM orders
        WHERE id = ?
        AND user_id = ?
        """,
        (
            order_id,
            session["user_id"]
        )
    ).fetchone()

    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Order not found"
        }), 404

    items = connection.execute(
        """
        SELECT
            product_id,
            product_name,
            price,
            quantity
        FROM order_items
        WHERE order_id = ?
        ORDER BY id ASC
        """,
        (order_id,)
    ).fetchall()

    connection.close()

    return jsonify({
        "success": True,
        "order": {
            "id": order["id"],
            "total": float(
                order["total"]
            ),
            "status": order["status"],
            "created_at": order["created_at"],
            "items": [
                dict(item)
                for item in items
            ]
        }
    })


# ==========================================
# ADMIN ORDERS
# ==========================================

@app.route(
    "/api/admin/orders",
    methods=["GET"]
)
def admin_orders():

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    connection = get_db()

    orders = connection.execute(
        """
        SELECT
            orders.id,
            orders.user_id,
            orders.total,
            orders.status,
            orders.created_at,
            users.name AS user_name,
            users.email AS user_email
        FROM orders
        JOIN users
        ON orders.user_id = users.id
        ORDER BY orders.id DESC
        """
    ).fetchall()

    result = []

    for order in orders:

        items = connection.execute(
            """
            SELECT
                product_id,
                product_name,
                price,
                quantity
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order["id"],)
        ).fetchall()

        result.append({
            "id": order["id"],
            "user_id": order["user_id"],
            "user_name": order["user_name"],
            "user_email": order["user_email"],
            "total": float(
                order["total"]
            ),
            "status": order["status"],
            "created_at": order["created_at"],
            "items": [
                dict(item)
                for item in items
            ]
        })

    connection.close()

    return jsonify({
        "success": True,
        "orders": result
    })


# ==========================================
# ADMIN UPDATE ORDER STATUS
# ==========================================

@app.route(
    "/api/admin/orders/<int:order_id>/status",
    methods=["PUT"]
)
def update_order_status(order_id):

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request"
        }), 400

    status = str(
        data.get(
            "status",
            ""
        )
    ).strip()

    allowed_statuses = {
        "Pending",
        "Shipped",
        "Delivered"
    }

    if status not in allowed_statuses:

        return jsonify({
            "success": False,
            "message": "Invalid order status"
        }), 400

    connection = get_db()

    order = connection.execute(
        """
        SELECT id
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()

    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Order not found"
        }), 404

    connection.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            order_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Order status updated successfully",
        "order_id": order_id,
        "status": status
    })


# ==========================================
# ADMIN DASHBOARD API
# ==========================================

@app.route(
    "/api/admin/dashboard",
    methods=["GET"]
)
def admin_dashboard():

    if not is_admin():

        return jsonify({
            "success": False,
            "message": "Admin access required"
        }), 403

    connection = get_db()

    users_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]

    orders_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        """
    ).fetchone()[0]

    pending_orders = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    shipped_orders = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Shipped'
        """
    ).fetchone()[0]

    delivered_orders = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Delivered'
        """
    ).fetchone()[0]

    total_sales = connection.execute(
        """
        SELECT COALESCE(
            SUM(total),
            0
        )
        FROM orders
        WHERE status = 'Delivered'
        """
    ).fetchone()[0]

    connection.close()

    products = get_products()

    products_count = len(
        products
    )

    categories_count = len(
        {
            product["category"]
            for product in products
            if product["category"]
        }
    )

    return jsonify({
        "success": True,
        "products": products_count,
        "users": users_count,
        "orders": orders_count,
        "categories": categories_count,
        "pending_orders": pending_orders,
        "shipped_orders": shipped_orders,
        "delivered_orders": delivered_orders,
        "total_sales": float(
            total_sales or 0
        )
    })


# ==========================================
# RUN SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=False
    )

