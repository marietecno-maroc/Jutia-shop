# app.py — متجر Jutia الكامل
import sqlite3, os, json, datetime, random, string
from functools import wraps
from flask import (Flask, request, jsonify, render_template, g,
                   session, redirect, url_for, flash, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


# Telegram Notifications
TELEGRAM_TOKEN = "8639124175:AAHNuXBJO0yCTmKUkV8ww8IHTT64VleZAvo"
TELEGRAM_CHAT_ID = "8866624601"

app = Flask(__name__, static_folder="static")
app.secret_key = "noor-shop-secret-key-2026-change-me"


# ============ قاعدة البيانات ============


def get_client_ip():
    """الحصول على IP العميل"""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0")
    return ip.split(",")[0].strip()




# ═══ Helper: التحقق من صورة ═══
def is_image(filename):
    """يتحقق واش الملف صورة"""
    if not filename:
        return False
    return str(filename).lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))


@app.context_processor
def utility_processor():
    """يمرر الدوال لكل القوالب"""
    return {
        'is_image': is_image,
    }


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


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file):
    """حفظ صورة مرفوعة وإرجاع الاسم"""
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    import time
    filename = f"product_{int(time.time())}_{random.randint(1000,9999)}.{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename





def send_telegram(message):
    try:
        import requests
        url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
        return True
    except Exception as e:
        print("Telegram error:", e)
        return False


@app.route("/")
def index():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id DESC LIMIT 8").fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    market_products = db.execute("""SELECT p.*, c.name as cat_name
                                    FROM used_products p
                                    LEFT JOIN categories c ON c.id = p.category_id
                                    WHERE p.status='متوفر'
                                    ORDER BY p.id DESC LIMIT 10""").fetchall()
    best_sellers = db.execute("""
        SELECT p.*, SUM(oi.qty) as total_sold
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        GROUP BY p.id
        ORDER BY total_sold DESC
        LIMIT 4
    """).fetchall()
    testimonials = db.execute("SELECT * FROM testimonials WHERE is_approved=1 ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html",
                           products=products,
                           categories=categories,
                           market_products=market_products,
                           best_sellers=best_sellers,
                           testimonials=testimonials)


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

    # ORDER NOTIFICATION
    try:
        items_text = "\n".join(["• " + it[1] + " × " + str(it[3]) for it in items])
        msg = "🛒 <b>طلب جديد #" + str(oid) + "</b>\n\n👤 <b>العميل:</b> " + str(d.get('name')) + "\n📞 <b>الهاتف:</b> " + str(d.get('phone')) + "\n📍 <b>العنوان:</b> " + str(d.get('address')) + "\n\n📦 <b>المنتجات:</b>\n" + items_text + "\n\n💰 <b>المجموع:</b> " + format(total, ".2f") + " د.م"
        if discount > 0:
            msg = msg + "\n🎁 <b>خصم:</b> " + format(discount, ".2f") + " د.م"
        send_telegram(msg)
    except Exception as e:
        print("Notify error:", e)

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
    image1 = d.get("image", "SHOP")
    image2 = None
    image3 = None
    if "image_file" in request.files:
        up = save_uploaded_image(request.files["image_file"])
        if up: image1 = up
    if "image_file2" in request.files:
        up = save_uploaded_image(request.files["image_file2"])
        if up: image2 = up
    if "image_file3" in request.files:
        up = save_uploaded_image(request.files["image_file3"])
        if up: image3 = up
    db.execute("""INSERT INTO products (name,description,price,old_price,image,image2,image3,category_id,stock)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (d["name"], d["description"], float(d["price"]),
                float(d.get("old_price") or 0), image1, image2, image3,
                int(d.get("category_id", 1)), int(d.get("stock", 100))))
    db.commit()
    flash("Product added", "ok")
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






# ============ تعديل منتج ============
@app.route("/admin/product/edit/<int:pid>", methods=["GET","POST"])
@admin_required
def admin_edit_product(pid):
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return "Product not found", 404
    if request.method == "POST":
        d = request.form
        image1 = p["image"]
        image2 = p["image2"] if "image2" in p.keys() else None
        image3 = p["image3"] if "image3" in p.keys() else None
        if "image_file" in request.files and request.files["image_file"].filename:
            up = save_uploaded_image(request.files["image_file"])
            if up: image1 = up
        if "image_file2" in request.files and request.files["image_file2"].filename:
            up = save_uploaded_image(request.files["image_file2"])
            if up: image2 = up
        if "image_file3" in request.files and request.files["image_file3"].filename:
            up = save_uploaded_image(request.files["image_file3"])
            if up: image3 = up
        db.execute("""UPDATE products SET name=?, description=?, price=?, old_price=?,
                      image=?, image2=?, image3=?, category_id=?, stock=? WHERE id=?""",
                   (d["name"], d["description"], float(d["price"]), float(d.get("old_price") or 0),
                    image1, image2, image3, int(d.get("category_id", 1)),
                    int(d.get("stock", 100)), pid))
        db.commit()
        flash("Product updated", "ok")
        return redirect(url_for("admin"))
    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("edit_product.html", p=p, categories=categories)
    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return "Product not found", 404
    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("edit_product.html", p=p, categories=categories)


# ============ تفاصيل الطلب ============
@app.route("/admin/order/<int:oid>")
@admin_required
def admin_order_detail(oid):
    db = get_db()
    o = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not o:
        return "Order not found", 404
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()
    return render_template("order_detail.html", o=o, items=items)


# ============ حذف طلب ============
@app.route("/admin/order/delete/<int:oid>", methods=["POST"])
@admin_required
def admin_delete_order(oid):
    db = get_db()
    db.execute("DELETE FROM order_items WHERE order_id=?", (oid,))
    db.execute("DELETE FROM orders WHERE id=?", (oid,))
    db.commit()
    flash("Order deleted", "ok")
    return redirect(url_for("admin"))


# ============ تغيير كلمة المرور ============
@app.route("/admin/change-password", methods=["GET","POST"])
@admin_required
def admin_change_password():
    if request.method == "POST":
        old = request.form.get("old_pass", "")
        new = request.form.get("new_pass", "")
        confirm = request.form.get("confirm_pass", "")
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
        if not u or not check_password_hash(u["password"], old):
            flash("Old password is wrong", "err")
        elif new != confirm:
            flash("Passwords do not match", "err")
        elif len(new) < 6:
            flash("Password too short", "err")
        else:
            db.execute("UPDATE users SET password=? WHERE id=?",
                       (generate_password_hash(new), session["uid"]))
            db.commit()
            flash("Password changed", "ok")
            return redirect(url_for("admin"))
    return render_template("change_password.html")


# ============ الإعدادات ============
@app.route("/admin/settings", methods=["GET","POST"])
@admin_required
def admin_settings():
    db = get_db()
    if request.method == "POST":
        keys = ["shop_name", "whatsapp", "email", "address",
                "welcome_message", "facebook", "instagram"]
        for k in keys:
            v = request.form.get(k, "")
            existing = db.execute("SELECT * FROM settings WHERE key=?", (k,)).fetchone()
            if existing:
                db.execute("UPDATE settings SET value=? WHERE key=?", (v, k))
            else:
                db.execute("INSERT INTO settings (key,value) VALUES (?,?)", (k, v))
        db.commit()
        flash("Settings saved", "ok")
        return redirect(url_for("admin_settings"))
    rows = db.execute("SELECT * FROM settings").fetchall()
    s = {r["key"]: r["value"] for r in rows}
    return render_template("settings.html", s=s)




# ============ قائمة العملاء ============
@app.route("/admin/customers")
@admin_required
def admin_customers():
    db = get_db()
    customers = db.execute("""
        SELECT u.*, COUNT(o.id) as orders_count,
               COALESCE(SUM(o.total),0) as total_spent
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.id
        WHERE u.is_admin = 0
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """).fetchall()
    return render_template("customers.html", customers=customers)


# ============ إدارة الكوبونات ============
@app.route("/admin/coupons")
@admin_required
def admin_coupons():
    db = get_db()
    coupons = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return render_template("coupons.html", coupons=coupons)


@app.route("/admin/coupon/add", methods=["POST"])
@admin_required
def admin_add_coupon():
    code = request.form.get("code", "").strip().upper()
    percent = int(request.form.get("percent", 10))
    max_uses = int(request.form.get("max_uses", 1))
    if code:
        db = get_db()
        try:
            db.execute("INSERT INTO coupons (code,percent,max_uses) VALUES (?,?,?)",
                       (code, percent, max_uses))
            db.commit()
            flash("Coupon added", "ok")
        except sqlite3.IntegrityError:
            flash("Code already exists", "err")
    return redirect(url_for("admin_coupons"))


@app.route("/admin/coupon/delete/<int:cid>", methods=["POST"])
@admin_required
def admin_delete_coupon(cid):
    db = get_db()
    db.execute("DELETE FROM coupons WHERE id=?", (cid,))
    db.commit()
    flash("Coupon deleted", "ok")
    return redirect(url_for("admin_coupons"))


# ============ إدارة الفئات ============
@app.route("/admin/categories")
@admin_required
def admin_categories():
    db = get_db()
    cats = db.execute("""
        SELECT c.*, COUNT(p.id) as products_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id ORDER BY c.id
    """).fetchall()
    return render_template("categories.html", cats=cats)


@app.route("/admin/category/add", methods=["POST"])
@admin_required
def admin_add_category():
    name = request.form.get("name", "").strip()
    icon = request.form.get("icon", "SHOP").strip() or "SHOP"
    if name:
        db = get_db()
        db.execute("INSERT INTO categories (name,icon) VALUES (?,?)", (name, icon))
        db.commit()
        flash("Category added", "ok")
    return redirect(url_for("admin_categories"))


@app.route("/admin/category/delete/<int:cid>", methods=["POST"])
@admin_required
def admin_delete_category(cid):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id=?", (cid,))
    db.commit()
    flash("Category deleted", "ok")
    return redirect(url_for("admin_categories"))


# ============ تحديث admin مع البحث ============
@app.route("/admin/orders")
@admin_required
def admin_orders_filtered():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    db = get_db()
    sql = "SELECT * FROM orders WHERE 1=1"
    args = []
    if q:
        sql += " AND (customer_name LIKE ? OR phone LIKE ? OR id LIKE ?)"
        args += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY id DESC"
    orders = db.execute(sql, args).fetchall()
    return render_template("orders.html", orders=orders, q=q, status=status)






# ============ تصدير الطلبات ============
@app.route("/admin/export/orders")
@admin_required
def admin_export_orders():
    from flask import Response
    import csv
    from io import StringIO

    db = get_db()
    orders = db.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

    si = StringIO()
    si.write("\ufeff")  # BOM للعربية فـ Excel
    writer = csv.writer(si)
    writer.writerow(["ID", "Customer", "Phone", "Address", "Total", "Discount", "Coupon", "Status", "Date"])

    for o in orders:
        writer.writerow([
            o["id"], o["customer_name"], o["phone"], o["address"],
            o["total"], o["discount"], o["coupon"] or "",
            o["status"], o["created_at"]
        ])

    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    return Response(
        si.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=orders_{date_str}.csv"}
    )


@app.route("/admin/export/products")
@admin_required
def admin_export_products():
    from flask import Response
    import csv
    from io import StringIO

    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()

    si = StringIO()
    si.write("\ufeff")
    writer = csv.writer(si)
    writer.writerow(["ID", "Name", "Description", "Price", "Old Price", "Stock", "Category", "Rating"])

    for p in products:
        writer.writerow([
            p["id"], p["name"], p["description"] or "",
            p["price"], p["old_price"] or 0, p["stock"],
            p["category_id"], p["rating"]
        ])

    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    return Response(
        si.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=products_{date_str}.csv"}
    )


@app.route("/admin/export/customers")
@admin_required
def admin_export_customers():
    from flask import Response
    import csv
    from io import StringIO

    db = get_db()
    customers = db.execute("""
        SELECT u.*, COUNT(o.id) as orders_count, COALESCE(SUM(o.total),0) as total_spent
        FROM users u LEFT JOIN orders o ON o.user_id = u.id
        WHERE u.is_admin = 0
        GROUP BY u.id ORDER BY u.id DESC
    """).fetchall()

    si = StringIO()
    si.write("\ufeff")
    writer = csv.writer(si)
    writer.writerow(["ID", "Name", "Email", "Phone", "Orders", "Total Spent", "Joined"])

    for c in customers:
        writer.writerow([
            c["id"], c["name"], c["email"], c["phone"] or "",
            c["orders_count"], c["total_spent"], c["created_at"]
        ])

    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    return Response(
        si.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=customers_{date_str}.csv"}
    )






# ============ عداد الطلبات الجديدة ============
@app.route("/api/admin/new-orders")
@admin_required
def admin_new_orders_count():
    db = get_db()
    count = db.execute("SELECT COUNT(*) c FROM orders WHERE status='جديد'").fetchone()["c"]
    recent = db.execute("""SELECT id, customer_name, total, created_at
                           FROM orders WHERE status='جديد'
                           ORDER BY id DESC LIMIT 5""").fetchall()
    return jsonify({
        "count": count,
        "recent": [dict(r) for r in recent]
    })


# ============ التحليلات ============
@app.route("/admin/analytics")
@admin_required
def admin_analytics():
    db = get_db()
    # مبيعات آخر 7 أيام
    sales_7days = db.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as count, COALESCE(SUM(total),0) as revenue
        FROM orders
        WHERE created_at >= DATE('now', '-7 days')
        GROUP BY DATE(created_at)
        ORDER BY day
    """).fetchall()

    # أعلى 5 منتجات
    top_products = db.execute("""
        SELECT oi.name, SUM(oi.qty) as sold, SUM(oi.price * oi.qty) as revenue
        FROM order_items oi
        GROUP BY oi.name
        ORDER BY sold DESC
        LIMIT 5
    """).fetchall()

    # الطلبات حسب الحالة
    by_status = db.execute("""
        SELECT status, COUNT(*) as count FROM orders GROUP BY status
    """).fetchall()

    # إحصائيات عامة
    stats = {
        "total_revenue": db.execute("SELECT COALESCE(SUM(total),0) s FROM orders").fetchone()["s"],
        "total_orders": db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"],
        "avg_order": db.execute("SELECT COALESCE(AVG(total),0) a FROM orders").fetchone()["a"],
        "total_customers": db.execute("SELECT COUNT(*) c FROM users WHERE is_admin=0").fetchone()["c"]
    }

    return render_template("analytics.html",
                           sales_7days=sales_7days,
                           top_products=top_products,
                           by_status=by_status,
                           stats=stats)


# ============ نسخة احتياطية ============
@app.route("/admin/backup/download")
@admin_required
def admin_backup_download():
    from flask import send_file
    import datetime
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    if not os.path.exists(db_path):
        flash("Database not found", "err")
        return redirect(url_for("admin"))
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(db_path, as_attachment=True,
                     download_name=f"jutia_backup_{date_str}.db")


@app.route("/admin/backup/upload", methods=["POST"])
@admin_required
def admin_backup_upload():
    if "backup_file" not in request.files:
        flash("No file uploaded", "err")
        return redirect(url_for("admin"))
    f = request.files["backup_file"]
    if not f.filename.endswith(".db"):
        flash("Only .db files allowed", "err")
        return redirect(url_for("admin"))
    # نسخة من DB القديم قبل الاستبدال
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    if os.path.exists(db_path):
        import shutil
        shutil.copy(db_path, db_path + ".old")
    f.save(db_path)
    flash("Backup restored successfully", "ok")
    return redirect(url_for("admin"))




# ══════════════════════════════════════════════════════════
# ═══════════════ SELLERS (Marketplace) ════════════════════
# ══════════════════════════════════════════════════════════

def seller_login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("seller_id"):
            flash("يجب تسجيل الدخول أولاً", "warn")
            return redirect(url_for("seller_login"))
        return f(*a, **kw)
    return wrapper


# ============ التسجيل ============
@app.route("/sell/register", methods=["GET", "POST"])
def seller_register():
    if request.method == "POST":
        d = request.form
        db = get_db()
        try:
            cur = db.execute("""INSERT INTO sellers
                (name, email, password, phone, shop_name, city, bio)
                VALUES (?,?,?,?,?,?,?)""",
                (d.get("name"), d.get("email"),
                 generate_password_hash(d.get("password")),
                 d.get("phone"), d.get("shop_name"),
                 d.get("city"), d.get("bio", "")))
            db.commit()
            session["seller_id"] = cur.lastrowid
            session["seller_name"] = d.get("name")
            session["seller_shop"] = d.get("shop_name")
            flash("مرحباً بك في Jutia Sellers! 🎉", "ok")
            return redirect(url_for("seller_dashboard"))
        except sqlite3.IntegrityError:
            flash("البريد الإلكتروني مستخدم بالفعل", "err")
    return render_template("sell_register.html")


# ============ الدخول ============
@app.route("/sell/login", methods=["GET", "POST"])
def seller_login():
    if request.method == "POST":
        d = request.form
        db = get_db()
        s = db.execute("SELECT * FROM sellers WHERE email=?",
                       (d.get("email"),)).fetchone()
        if s and check_password_hash(s["password"], d.get("password", "")):
            session["seller_id"] = s["id"]
            session["seller_name"] = s["name"]
            session["seller_shop"] = s["shop_name"]
            flash("مرحباً بك 👋", "ok")
            return redirect(url_for("seller_dashboard"))
        flash("البريد أو كلمة المرور غير صحيحة", "err")
    return render_template("sell_login.html")


@app.route("/sell/logout")
def seller_logout():
    session.pop("seller_id", None)
    session.pop("seller_name", None)
    session.pop("seller_shop", None)
    flash("تم تسجيل الخروج", "ok")
    return redirect(url_for("marketplace"))


# ============ لوحة تحكم التاجر ============
@app.route("/sell/dashboard")
@seller_login_required
def seller_dashboard():
    db = get_db()
    sid = session["seller_id"]

    stats = {
        "products": db.execute("SELECT COUNT(*) c FROM used_products WHERE seller_id=?",
                               (sid,)).fetchone()["c"],
        "available": db.execute("SELECT COUNT(*) c FROM used_products WHERE seller_id=? AND status='متوفر'",
                                (sid,)).fetchone()["c"],
        "messages": db.execute("SELECT COUNT(*) c FROM seller_messages WHERE seller_id=?",
                               (sid,)).fetchone()["c"],
        "unread": db.execute("SELECT COUNT(*) c FROM seller_messages WHERE seller_id=? AND is_read=0",
                             (sid,)).fetchone()["c"],
    }

    products = db.execute("""SELECT p.*, c.name as category_name
                             FROM used_products p
                             LEFT JOIN categories c ON c.id = p.category_id
                             WHERE p.seller_id=?
                             ORDER BY p.id DESC""", (sid,)).fetchall()

    recent_messages = db.execute("""SELECT * FROM seller_messages
                                    WHERE seller_id=?
                                    ORDER BY id DESC LIMIT 5""",
                                 (sid,)).fetchall()

    seller = db.execute("SELECT * FROM sellers WHERE id=?", (sid,)).fetchone()

    return render_template("sell_dashboard.html",
                           stats=stats, products=products,
                           recent_messages=recent_messages,
                           seller=seller)


# ============ إضافة منتج ============
@app.route("/sell/product/add", methods=["GET", "POST"])
@seller_login_required
def seller_add_product():
    db = get_db()
    if request.method == "POST":
        d = request.form
        # معالجة الصور الثلاثة
        images = []
        for i in ["image1", "image2", "image3"]:
            img_name = None
            key = f"{i}_file"
            if key in request.files:
                uploaded = save_uploaded_image(request.files[key])
                if uploaded:
                    img_name = uploaded
            images.append(img_name)

        db.execute("""INSERT INTO used_products
            (seller_id, name, description, price, category_id,
             condition_type, city, stock, image1, image2, image3)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (session["seller_id"], d.get("name"), d.get("description"),
             float(d.get("price", 0)), int(d.get("category_id", 1)),
             d.get("condition_type", "مستعمل"), d.get("city"),
             int(d.get("stock", 1)),
             images[0], images[1], images[2]))
        db.commit()
        flash("تمت إضافة المنتج بنجاح ✅", "ok")
        return redirect(url_for("seller_dashboard"))

    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("sell_product_add.html", categories=categories)


# ============ تعديل منتج ============
@app.route("/sell/product/edit/<int:pid>", methods=["GET", "POST"])
@seller_login_required
def seller_edit_product(pid):
    db = get_db()
    p = db.execute("SELECT * FROM used_products WHERE id=? AND seller_id=?",
                   (pid, session["seller_id"])).fetchone()
    if not p:
        flash("المنتج غير موجود", "err")
        return redirect(url_for("seller_dashboard"))

    if request.method == "POST":
        d = request.form
        images = [p["image1"], p["image2"], p["image3"]]
        for idx, i in enumerate(["image1", "image2", "image3"]):
            key = f"{i}_file"
            if key in request.files:
                uploaded = save_uploaded_image(request.files[key])
                if uploaded:
                    images[idx] = uploaded

        db.execute("""UPDATE used_products SET
            name=?, description=?, price=?, category_id=?,
            condition_type=?, city=?, stock=?, status=?,
            image1=?, image2=?, image3=?
            WHERE id=? AND seller_id=?""",
            (d.get("name"), d.get("description"), float(d.get("price", 0)),
             int(d.get("category_id", 1)), d.get("condition_type"),
             d.get("city"), int(d.get("stock", 1)),
             d.get("status", "متوفر"),
             images[0], images[1], images[2],
             pid, session["seller_id"]))
        db.commit()
        flash("تم تحديث المنتج ✅", "ok")
        return redirect(url_for("seller_dashboard"))

    categories = db.execute("SELECT * FROM categories").fetchall()
    return render_template("sell_product_edit.html", p=p, categories=categories)


# ============ حذف منتج ============
@app.route("/sell/product/delete/<int:pid>", methods=["POST"])
@seller_login_required
def seller_delete_product(pid):
    db = get_db()
    db.execute("DELETE FROM used_products WHERE id=? AND seller_id=?",
               (pid, session["seller_id"]))
    db.commit()
    flash("تم حذف المنتج", "ok")
    return redirect(url_for("seller_dashboard"))


# ============ الرسائل ============
@app.route("/sell/messages")
@seller_login_required
def seller_messages():
    db = get_db()
    msgs = db.execute("""SELECT m.*, p.name as product_name
                         FROM seller_messages m
                         LEFT JOIN used_products p ON p.id = m.product_id
                         WHERE m.seller_id=?
                         ORDER BY m.id DESC""",
                      (session["seller_id"],)).fetchall()
    return render_template("sell_messages.html", messages=msgs)


@app.route("/sell/message/<int:mid>")
@seller_login_required
def seller_message_view(mid):
    db = get_db()
    m = db.execute("""SELECT m.*, p.name as product_name, p.id as pid
                      FROM seller_messages m
                      LEFT JOIN used_products p ON p.id = m.product_id
                      WHERE m.id=? AND m.seller_id=?""",
                   (mid, session["seller_id"])).fetchone()
    if not m:
        flash("الرسالة غير موجودة", "err")
        return redirect(url_for("seller_messages"))

    db.execute("UPDATE seller_messages SET is_read=1 WHERE id=?", (mid,))
    db.commit()
    return render_template("sell_message_view.html", m=m)


@app.route("/sell/message/<int:mid>/delete", methods=["POST"])
@seller_login_required
def seller_message_delete(mid):
    db = get_db()
    db.execute("DELETE FROM seller_messages WHERE id=? AND seller_id=?",
               (mid, session["seller_id"]))
    db.commit()
    flash("تم حذف الرسالة", "ok")
    return redirect(url_for("seller_messages"))


# ============ تعديل البروفايل ============
@app.route("/sell/profile", methods=["GET", "POST"])
@seller_login_required
def seller_profile():
    db = get_db()
    if request.method == "POST":
        d = request.form
        db.execute("""UPDATE sellers SET
            name=?, phone=?, shop_name=?, city=?, bio=?
            WHERE id=?""",
            (d.get("name"), d.get("phone"), d.get("shop_name"),
             d.get("city"), d.get("bio", ""),
             session["seller_id"]))
        db.commit()
        session["seller_name"] = d.get("name")
        session["seller_shop"] = d.get("shop_name")
        flash("تم تحديث البيانات ✅", "ok")
        return redirect(url_for("seller_profile"))

    seller = db.execute("SELECT * FROM sellers WHERE id=?",
                        (session["seller_id"],)).fetchone()
    return render_template("sell_profile.html", seller=seller)


# ══════════════════════════════════════════════════════════
# ═══════════════ Marketplace (عام) ════════════════════════
# ══════════════════════════════════════════════════════════

@app.route("/marketplace")
def marketplace():
    db = get_db()
    cat = request.args.get("cat", "")
    q = request.args.get("q", "")
    city = request.args.get("city", "")
    min_price = request.args.get("min_price", "")
    max_price = request.args.get("max_price", "")

    sql = """SELECT p.*, c.name as category_name, s.shop_name, s.name as seller_name
             FROM used_products p
             LEFT JOIN categories c ON c.id = p.category_id
             LEFT JOIN sellers s ON s.id = p.seller_id
             WHERE p.status = 'متوفر'"""
    args = []
    if cat:
        sql += " AND p.category_id=?"
        args.append(cat)
    if q:
        sql += " AND (p.name LIKE ? OR p.description LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if city:
        sql += " AND p.city LIKE ?"
        args.append(f"%{city}%")
    if min_price:
        try:
            sql += " AND p.price >= ?"
            args.append(float(min_price))
        except: pass
    if max_price:
        try:
            sql += " AND p.price <= ?"
            args.append(float(max_price))
        except: pass
    sql += " ORDER BY p.id DESC"

    products = db.execute(sql, args).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()

    # المدن المتوفرة
    cities = db.execute("""SELECT DISTINCT city FROM used_products
                           WHERE city IS NOT NULL AND city != ''
                           ORDER BY city""").fetchall()

    return render_template("marketplace.html",
                           products=products, categories=categories,
                           cities=cities, current_cat=cat, q=q,
                           current_city=city,
                           min_price=min_price, max_price=max_price)


@app.route("/marketplace/product/<int:pid>")
def marketplace_product(pid):
    db = get_db()
    p = db.execute("""SELECT p.*, c.name as category_name,
                      s.shop_name, s.name as seller_name,
                      s.phone as seller_phone, s.city as seller_city,
                      s.id as sid
                      FROM used_products p
                      LEFT JOIN categories c ON c.id = p.category_id
                      LEFT JOIN sellers s ON s.id = p.seller_id
                      WHERE p.id=?""", (pid,)).fetchone()
    if not p:
        return "المنتج غير موجود", 404

    # زيادة عدد المشاهدات
    db.execute("UPDATE used_products SET views = views + 1 WHERE id=?", (pid,))
    db.commit()

    # منتجات مشابهة
    related = db.execute("""SELECT p.*, c.name as category_name
                            FROM used_products p
                            LEFT JOIN categories c ON c.id = p.category_id
                            WHERE p.category_id=? AND p.id != ? AND p.status='متوفر'
                            LIMIT 4""",
                         (p["category_id"], pid)).fetchall()

    return render_template("marketplace_product.html", p=p, related=related)


# ============ إرسال رسالة للتاجر ============
@app.route("/marketplace/contact/<int:pid>", methods=["POST"])
def marketplace_contact(pid):
    db = get_db()
    p = db.execute("SELECT * FROM used_products WHERE id=?", (pid,)).fetchone()
    if not p:
        return jsonify({"ok": False, "msg": "المنتج غير موجود"})

    d = request.json
    db.execute("""INSERT INTO seller_messages
        (seller_id, product_id, sender_name, sender_phone, sender_email, message)
        VALUES (?,?,?,?,?,?)""",
        (p["seller_id"], pid, d.get("name"), d.get("phone"),
         d.get("email", ""), d.get("message")))
    db.commit()
    return jsonify({"ok": True, "msg": "تم إرسال رسالتك بنجاح ✅"})


# ============ لوحة تحكم التجار (عام) ============
@app.route("/sellers")
def sellers_list():
    db = get_db()
    sellers = db.execute("""SELECT s.*,
                            COUNT(p.id) as products_count
                            FROM sellers s
                            LEFT JOIN used_products p ON p.seller_id = s.id AND p.status='متوفر'
                            WHERE s.is_active = 1
                            GROUP BY s.id
                            ORDER BY products_count DESC""").fetchall()
    return render_template("sellers_list.html", sellers=sellers)





# ═══ Digital Asset Links (للتحقق من ملكية التطبيق) ═══
@app.route("/.well-known/assetlinks.json")
def assetlinks():
    from flask import send_from_directory
    return send_from_directory("static", "assetlinks.json",
                               mimetype="application/json")




# ═══ سياسة الخصوصية ═══
@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")




# ═══ Contact & About Routes ═══
@app.route("/contact")
def contact_page():
    return render_template("contact.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


# ============ تشغيل ============


# ============ Context Processor ============
@app.context_processor
def inject_settings():
    """يمرر الإعدادات لجميع القوالب"""
    try:
        db = get_db()
        rows = db.execute("SELECT * FROM settings").fetchall()
        s = {r["key"]: r["value"] for r in rows}
        return {"site": s}
    except:
        return {"site": {}}




# ============ FAVORITES & RATINGS ============

@app.route("/api/favorite/toggle/<int:pid>", methods=["POST"])
def toggle_favorite(pid):
    db = get_db()
    ip = get_client_ip()
    existing = db.execute("SELECT id FROM favorites WHERE user_ip=? AND product_id=?", (ip, pid)).fetchone()
    if existing:
        db.execute("DELETE FROM favorites WHERE id=?", (existing["id"],))
        db.commit()
        return jsonify({"ok": True, "action": "removed"})
    db.execute("INSERT INTO favorites (user_ip, product_id) VALUES (?,?)", (ip, pid))
    db.commit()
    return jsonify({"ok": True, "action": "added"})


@app.route("/api/favorite/status/<int:pid>")
def favorite_status(pid):
    db = get_db()
    ip = get_client_ip()
    exists = db.execute("SELECT id FROM favorites WHERE user_ip=? AND product_id=?", (ip, pid)).fetchone()
    return jsonify({"favorited": bool(exists)})


@app.route("/favorites")
def favorites_page():
    db = get_db()
    ip = get_client_ip()
    favorites = db.execute("SELECT p.*, c.name as category_name, s.shop_name FROM favorites f JOIN used_products p ON p.id = f.product_id LEFT JOIN categories c ON c.id = p.category_id LEFT JOIN sellers s ON s.id = p.seller_id WHERE f.user_ip=? ORDER BY f.id DESC", (ip,)).fetchall()
    return render_template("favorites.html", products=favorites)


@app.route("/api/seller/rate/<int:sid>", methods=["POST"])
def rate_seller(sid):
    db = get_db()
    ip = get_client_ip()
    d = request.json
    rating = int(d.get("rating", 5))
    comment = d.get("comment", "").strip()
    existing = db.execute("SELECT id FROM seller_ratings WHERE seller_id=? AND rater_ip=?", (sid, ip)).fetchone()
    if existing:
        db.execute("UPDATE seller_ratings SET rating=?, comment=? WHERE id=?", (rating, comment, existing["id"]))
    else:
        db.execute("INSERT INTO seller_ratings (seller_id, rater_ip, rating, comment) VALUES (?,?,?,?)", (sid, ip, rating, comment))
    db.commit()
    return jsonify({"ok": True, "msg": "تم التقييم"})


@app.route("/api/seller/rating/<int:sid>")
def get_seller_rating(sid):
    db = get_db()
    r = db.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM seller_ratings WHERE seller_id=?", (sid,)).fetchone()
    return jsonify({"avg": round(r["avg_rating"], 1) if r["avg_rating"] else 0, "count": r["count"]})


@app.route("/seller/<int:sid>")
def seller_public(sid):
    db = get_db()
    seller = db.execute("SELECT * FROM sellers WHERE id=? AND is_active=1", (sid,)).fetchone()
    if not seller:
        return "Seller not found", 404
    products = db.execute("SELECT p.*, c.name as category_name FROM used_products p LEFT JOIN categories c ON c.id = p.category_id WHERE p.seller_id=? AND p.status='متوفر' ORDER BY p.id DESC", (sid,)).fetchall()
    ratings = db.execute("SELECT * FROM seller_ratings WHERE seller_id=? ORDER BY id DESC LIMIT 10", (sid,)).fetchall()
    rating_data = db.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM seller_ratings WHERE seller_id=?", (sid,)).fetchone()
    ip = get_client_ip()
    my_rating = db.execute("SELECT * FROM seller_ratings WHERE seller_id=? AND rater_ip=?", (sid, ip)).fetchone()
    return render_template("seller_public.html", seller=seller, products=products, ratings=ratings, rating_data=rating_data, my_rating=my_rating)


# ============ تشغيل ============
if __name__ == "__main__":
    init_db()
    print("Jutia Store")
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)


# ═══ Backup Route ═══
@app.route("/admin/backup")
def admin_backup():
    from flask import send_file
    import os
    from datetime import datetime
    db_path = "/home/Jutia/jutia/shop.db"
    if not os.path.exists(db_path):
        return "Database not found", 404
    date = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(db_path, as_attachment=True,
                     download_name=f"jutia_backup_{date}.db")


# ═══ Terms Route ═══
@app.route("/terms")
def terms_page():
    return render_template("terms.html")


# ═══ Returns Route ═══
@app.route("/returns")
def returns_page():
    return render_template("returns.html")
