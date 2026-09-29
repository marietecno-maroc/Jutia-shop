# app.py — متجر Jutia الكامل
import sqlite3, os, json, datetime, random, string
from functools import wraps
from flask import (Flask, request, jsonify, render_template, g,
                   session, redirect, url_for, flash, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")
app = Flask(__name__, static_folder="static")
app.secret_key = "noor-shop-secret-key-2026-change-me"


# ============ قاعدة البيانات ============
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(e):
    db = getattr(g, "_database", None)
    if db: db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE,
            password TEXT, phone TEXT, is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, icon TEXT DEFAULT '🛍️');

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, description TEXT,
            price REAL NOT NULL, old_price REAL,
            image TEXT, category_id INTEGER,
            stock INTEGER DEFAULT 100,
            rating REAL DEFAULT 4.8,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, customer_name TEXT, phone TEXT, address TEXT,
            total REAL, discount REAL DEFAULT 0,
            coupon TEXT, status TEXT DEFAULT 'جديد',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER, product_id INTEGER,
            name TEXT, price REAL, qty INTEGER);

        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE, percent INTEGER,
            used INTEGER DEFAULT 0, max_uses INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        # فئات افتراضية
        cur = db.execute("SELECT COUNT(*) c FROM categories")
        if cur.fetchone()[0] == 0:
            db.executemany("INSERT INTO categories (name, icon) VALUES (?,?)", [
                ("إلكترونيات", "📱"), ("ملابس", "👕"),
                ("منزل", "🏠"), ("رياضة", "⚽"),
                ("جمال", "💄"), ("ألعاب", "🎮"),
            ])
        # منتجات تجريبية
        cur = db.execute("SELECT COUNT(*) c FROM products")
        if cur.fetchone()[0] == 0:
            demo = [
                ("سماعات لاسلكية Pro", "صوت نقي وبطارية 30 ساعة", 299, 499, "🎧", 1),
                ("ساعة ذكية X9", "شاشة AMOLED + مقاومة للماء", 549, 899, "⌚", 1),
                ("قميص قطني فاخر", "قطن 100% مريح جدًا", 149, 249, "👔", 2),
                ("حذاء رياضي Air", "خفيف ومريح للجري", 399, 599, "👟", 4),
                ("عطر Oud Royal", "رائحة شرقية فاخرة تدوم طويلًا", 349, 549, "🌸", 5),
                ("لعبة PlayStation 5", "أحدث جهاز ألعاب", 4999, 5499, "🎮", 6),
                ("مكنسة روبوت", "تنظف البيت تلقائيًا", 1299, 1799, "🤖", 3),
                ("نظارة شمسية Ray", "حماية UV400", 199, 349, "🕶️", 2),
                ("حقيبة ظهر Laptop", "مقاومة للماء + USB", 249, 399, "🎒", 2),
                ("مكبر صوت بلوتوث", "باس قوي + إضاءة", 179, 299, "🔊", 1),
                ("كريم مرطب فاخر", "ترطيب 24 ساعة", 89, 149, "🧴", 5),
                ("كرة قدم رسمية", "معتمدة FIFA", 249, 349, "⚽", 4),
            ]
            db.executemany("""INSERT INTO products (name,description,price,old_price,image,category_id)
                              VALUES (?,?,?,?,?,?)""", demo)
        # مدير افتراضي
        cur = db.execute("SELECT COUNT(*) c FROM users WHERE is_admin=1")
        if cur.fetchone()[0] == 0:
            db.execute("""INSERT INTO users (name,email,password,is_admin)
                          VALUES (?,?,?,1)""",
                       ("Admin", "admin@shop.com",
                        generate_password_hash("admin123")))


# ============ أدوات ============
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            flash("يجب تسجيل الدخول أولًا", "warn")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def gen_code(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


# ============ الصفحات العامة ============
@app.route("/")
def index():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id DESC LIMIT 8").fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("index.html", products=products, categories=categories)


@app.route("/shop")
def shop():
    db = get_db()
    cat = request.args.get("cat", "")
    q = request.args.get("q", "")
    sql = "SELECT * FROM products WHERE 1=1"
    args = []
    if cat:
        sql += " AND category_id=?"
        args.append(cat)
    if q:
        sql += " AND name LIKE ?"
        args.append(f"%{q}%")
    sql += " ORDER BY id DESC"
    products = db.execute(sql, args).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("shop.html", products=products,
                           categories=categories, current_cat=cat, q=q)


@app.route("/product/<int:pid>")
def product(pid):
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return "المنتج غير موجود", 404
    related = db.execute(
        "SELECT * FROM products WHERE category_id=? AND id!=? LIMIT 4",
        (p["category_id"], pid)).fetchall()
    return render_template("product.html", p=p, related=related)


# ============ السلة ============
@app.route("/cart")
def cart():
    cart = session.get("cart", {})
    db = get_db()
    items = []
    total = 0
    for pid, qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            item = dict(p)
            item["qty"] = qty
            item["subtotal"] = qty * p["price"]
            total += item["subtotal"]
            items.append(item)
    return render_template("cart.html", items=items, total=total)


@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    d = request.json
    pid = str(d.get("id"))
    qty = int(d.get("qty", 1))
    cart = session.get("cart", {})
    cart[pid] = cart.get(pid, 0) + qty
    session["cart"] = cart
    session.modified = True
    return jsonify({"ok": True, "count": sum(cart.values())})


@app.route("/api/cart/update", methods=["POST"])
def cart_update():
    d = request.json
    pid = str(d.get("id"))
    qty = int(d.get("qty", 1))
    cart = session.get("cart", {})
    if qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = qty
    session["cart"] = cart
    session.modified = True
    return jsonify({"ok": True})


@app.route("/api/cart/count")
def cart_count():
    return jsonify({"count": sum(session.get("cart", {}).values())})


# ============ الحساب ============
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "")
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users (name,email,password,phone) VALUES (?,?,?,?)",
                (name, email, generate_password_hash(password), phone))
            db.commit()
            session["uid"] = cur.lastrowid
            session["name"] = name
            flash("تم إنشاء حسابك 🎉", "ok")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("البريد مستخدم بالفعل", "err")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["password"], password):
            session["uid"] = u["id"]
            session["name"] = u["name"]
            session["is_admin"] = bool(u["is_admin"])
            flash("مرحبًا بك 👋", "ok")
            return redirect(url_for("admin") if u["is_admin"] else url_for("index"))
        flash("البريد أو كلمة المرور غير صحيحة", "err")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ============ الألعاب ============
@app.route("/games")
def games():
    return render_template("games.html")


@app.route("/api/spin", methods=["POST"])
def spin():
    """عجلة الحظ — الجوائز محسوبة."""
    prizes = [
        {"p": 30, "w": 5, "label": "0%", "color": "#64748b"},
        {"p": 15, "w": 20, "label": "5%", "color": "#22c55e"},
        {"p": 25, "w": 15, "label": "10%", "color": "#06b6d4"},
        {"p": 10, "w": 25, "label": "15%", "color": "#8b5cf6"},
        {"p": 5, "w": 20, "label": "20%", "color": "#ec4899"},
        {"p": 2, "w": 10, "label": "30%", "color": "#f59e0b"},
        {"p": 40, "w": 3, "label": "50%", "color": "#ef4444"},
        {"p": 20, "w": 2, "label": "مجاني", "color": "#eab308"},
    ]
    total_w = sum(x["w"] for x in prizes)
    r = random.uniform(0, total_w)
    acc = 0
    idx = 0
    for i, x in enumerate(prizes):
        acc += x["w"]
        if r <= acc:
            idx = i
            break
    chosen = prizes[idx]
    if chosen["p"] > 0:
        code = "SPIN-" + gen_code(6)
        db = get_db()
        db.execute("INSERT INTO coupons (code,percent) VALUES (?,?)",
                   (code, chosen["p"]))
        db.commit()
    else:
        code = None
    return jsonify({"index": idx, "label": chosen["label"],
                    "percent": chosen["p"], "code": code})


@app.route("/api/scratch", methods=["POST"])
def scratch():
    """بطاقة الحظ — فوز شبه مؤكد."""
    outcomes = [
        {"p": 5, "w": 35}, {"p": 10, "w": 30},
        {"p": 15, "w": 20}, {"p": 20, "w": 10},
        {"p": 25, "w": 5},
    ]
    total_w = sum(x["w"] for x in outcomes)
    r = random.uniform(0, total_w)
    acc = 0
    chosen = outcomes[0]
    for x in outcomes:
        acc += x["w"]
        if r <= acc:
            chosen = x
            break
    code = "SCRATCH-" + gen_code(6)
    db = get_db()
    db.execute("INSERT INTO coupons (code,percent) VALUES (?,?)",
               (code, chosen["p"]))
    db.commit()
    return jsonify({"percent": chosen["p"], "code": code})


@app.route("/api/quiz", methods=["POST"])
def quiz():
    """لعبة أسئلة — الفوز يعطي 15%."""
    score = int(request.json.get("score", 0))
    total = int(request.json.get("total", 5))
    if score >= 4:
        p = 20
    elif score >= 3:
        p = 15
    elif score >= 2:
        p = 10
    else:
        p = 5
    code = "QUIZ-" + gen_code(6)
    db = get_db()
    db.execute("INSERT INTO coupons (code,percent) VALUES (?,?)", (code, p))
    db.commit()
    return jsonify({"percent": p, "code": code, "score": score})


@app.route("/api/coupon/check", methods=["POST"])
def coupon_check():
    code = request.json.get("code", "").strip().upper()
    db = get_db()
    c = db.execute("""SELECT * FROM coupons WHERE code=? AND used<max_uses""",
                   (code,)).fetchone()
    if c:
        return jsonify({"ok": True, "percent": c["percent"]})
    return jsonify({"ok": False, "msg": "كود غير صحيح أو مستعمل"})


# ============ الطلب ============
@app.route("/checkout")
def checkout():
    cart = session.get("cart", {})
    if not cart:
        return redirect(url_for("shop"))
    return render_template("checkout.html")


@app.route("/api/order", methods=["POST"])
def create_order():
    d = request.json
    cart = session.get("cart", {})
    if not cart:
        return jsonify({"ok": False, "msg": "السلة فارغة"})

    db = get_db()
    items = []
    subtotal = 0
    for pid, qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            items.append((p["id"], p["name"], p["price"], qty))
            subtotal += p["price"] * qty

    discount = 0
    coupon = d.get("coupon", "").strip().upper()
    if coupon:
        c = db.execute("SELECT * FROM coupons WHERE code=? AND used<max_uses",
                       (coupon,)).fetchone()
        if c:
            discount = subtotal * c["percent"] / 100
            db.execute("UPDATE coupons SET used=used+1 WHERE id=?", (c["id"],))

    total = subtotal - discount

    cur = db.execute("""INSERT INTO orders
        (user_id,customer_name,phone,address,total,discount,coupon)
        VALUES (?,?,?,?,?,?,?)""",
        (session.get("uid"), d.get("name"), d.get("phone"),
         d.get("address"), total, discount, coupon))
    oid = cur.lastrowid
    for it in items:
        db.execute("""INSERT INTO order_items (order_id,product_id,name,price,qty)
                      VALUES (?,?,?,?,?)""", (oid, *it))
    db.commit()

    session["cart"] = {}
    session.modified = True
    return jsonify({"ok": True, "order_id": oid, "total": total})


@app.route("/success/<int:oid>")
def success(oid):
    db = get_db()
    o = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not o:
        return redirect(url_for("index"))
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()
    return render_template("success.html", o=o, items=items)


# ============ لوحة التحكم ============
@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    stats = {
        "products": db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"],
        "orders": db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"],
        "users": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "revenue": db.execute("SELECT COALESCE(SUM(total),0) s FROM orders").fetchone()["s"],
    }
    orders = db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20").fetchall()
    products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin.html", stats=stats, orders=orders, products=products)


@app.route("/admin/product/add", methods=["POST"])
@admin_required
def admin_add_product():
    d = request.form
    db = get_db()
    db.execute("""INSERT INTO products (name,description,price,old_price,image,category_id,stock)
                  VALUES (?,?,?,?,?,?,?)""",
               (d["name"], d["description"], float(d["price"]),
                float(d.get("old_price") or 0), d.get("image", "🛍️"),
                int(d.get("category_id", 1)), int(d.get("stock", 100))))
    db.commit()
    flash("تمت إضافة المنتج ✅", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/product/delete/<int:pid>", methods=["POST"])
@admin_required
def admin_del_product(pid):
    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    return redirect(url_for("admin"))


@app.route("/admin/order/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    status = request.form.get("status", "جديد")
    db = get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    db.commit()
    return redirect(url_for("admin"))




# ============ تشغيل ============
if __name__ == "__main__":
    init_db()
    print("Jutia متجر")
    print("Admin: admin@shop.com / admin123")
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)
