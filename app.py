from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import sqlite3, os
from contextlib import closing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'store.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-demo-secret-key')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    with closing(db()) as con:
        con.executescript('''
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
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0)
        );
        ''')
        count = con.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        if count == 0:
            con.executemany('INSERT INTO products(name,category,description,price,stock,image_url) VALUES(?,?,?,?,?,?)', [
                ('Wireless Headphones','Electronics','Comfortable wireless headphones for everyday listening.', 8500, 12, ''),
                ('Classic Backpack','Accessories','A durable backpack for study, work and travel.', 4200, 18, ''),
                ('Smart Watch','Electronics','A simple smart watch with activity tracking features.', 12500, 7, ''),
                ('Ceramic Mug','Home','Reusable ceramic mug for hot and cold drinks.', 950, 30, '')
            ])
        con.commit()
        con.close()


def get_product(product_id):
    with closing(db()) as con:
        row = con.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
        con.close()
        return row

@app.context_processor
def inject_cart_count():
    return {'cart_count': sum(session.get('cart', {}).values())}

@app.route('/')
def index():
    search = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'newest')
    allowed_sort = {'price_asc':'price ASC', 'price_desc':'price DESC', 'name':'name COLLATE NOCASE ASC', 'newest':'id DESC'}
    sql = 'SELECT * FROM products WHERE stock >= 0'
    params = []
    if search:
        sql += ' AND (name LIKE ? OR description LIKE ? OR category LIKE ?)'
        params += [f'%{search}%'] * 3
    if category:
        sql += ' AND category = ?'; params.append(category)
    sql += ' ORDER BY ' + allowed_sort.get(sort, 'id DESC')
    with closing(db()) as con:
        products = con.execute(sql, params).fetchall()
        categories = [r['category'] for r in con.execute('SELECT DISTINCT category FROM products ORDER BY category').fetchall()]
        con.close()
    return render_template('index.html', products=products, categories=categories, q=search, selected_category=category, sort=sort)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product(product_id)
    if not product: abort(404)
    return render_template('detail.html', product=product)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = get_product(product_id)
    if not product: abort(404)
    try: quantity = int(request.form.get('quantity', '1'))
    except ValueError: quantity = 0
    if quantity < 1:
        flash('Quantity must be at least 1.', 'error')
    elif quantity > product['stock']:
        flash('Requested quantity exceeds available stock.', 'error')
    else:
        cart = session.get('cart', {})
        key = str(product_id)
        new_qty = int(cart.get(key, 0)) + quantity
        if new_qty > product['stock']:
            flash('Cart quantity exceeds available stock.', 'error')
        else:
            cart[key] = new_qty; session['cart'] = cart
            flash('Product added to your cart.', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart():
    cart_data = session.get('cart', {})
    items, total = [], 0
    with closing(db()) as con:
        for pid, qty in cart_data.items():
            p = con.execute('SELECT * FROM products WHERE id=?', (int(pid),)).fetchone()
            if p:
                subtotal = p['price'] * qty
                items.append({'product':p, 'quantity':qty, 'subtotal':subtotal}); total += subtotal
        con.close()
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/update', methods=['POST'])
def update_cart():
    cart_data = session.get('cart', {})
    with closing(db()) as con:
        for pid in list(cart_data.keys()):
            field = 'qty_' + pid
            if field in request.form:
                try: qty = int(request.form[field])
                except ValueError: qty = 0
                p = con.execute('SELECT stock FROM products WHERE id=?', (int(pid),)).fetchone()
                if qty <= 0: cart_data.pop(pid, None)
                elif p and qty <= p['stock']: cart_data[pid] = qty
                else: flash('Quantity was not updated because it exceeds available stock.', 'error')
        con.close()
    session['cart'] = cart_data
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET','POST'])
def checkout():
    cart_data = session.get('cart', {})
    if not cart_data:
        flash('Your cart is empty.', 'error'); return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('customer_name','').strip()
        email = request.form.get('email','').strip()
        address = request.form.get('address','').strip()
        if not name or not email or '@' not in email or not address:
            flash('Enter a valid name, email address and delivery address.', 'error')
            return redirect(url_for('checkout'))
        with closing(db()) as con:
            try:
                line_items, total = [], 0
                for pid, qty in cart_data.items():
                    p = con.execute('SELECT * FROM products WHERE id=?', (int(pid),)).fetchone()
                    if not p or qty < 1 or qty > p['stock']:
                        raise ValueError('Stock changed. Please review your cart.')
                    line_items.append((p, qty)); total += p['price'] * qty
                cur = con.execute('INSERT INTO orders(customer_name,email,address,total) VALUES(?,?,?,?)', (name,email,address,total))
                oid = cur.lastrowid
                for p, qty in line_items:
                    con.execute('INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price) VALUES(?,?,?,?,?)', (oid,p['id'],p['name'],qty,p['price']))
                    con.execute('UPDATE products SET stock=stock-? WHERE id=?', (qty,p['id']))
                con.commit(); con.close()
            except (ValueError, sqlite3.Error) as exc:
                con.rollback(); con.close(); flash(str(exc) if isinstance(exc, ValueError) else 'Could not place order. Please try again.', 'error')
                return redirect(url_for('cart'))
        session['cart'] = {}
        return render_template('success.html', order_id=oid, total=total)
    return render_template('checkout.html')

@app.route('/admin/products')
def admin_products():
    with closing(db()) as con:
        products = con.execute('SELECT * FROM products ORDER BY id DESC').fetchall(); con.close()
    return render_template('admin.html', products=products)

def validate_product(form):
    name = form.get('name','').strip(); category = form.get('category','').strip()
    description = form.get('description','').strip(); image_url = form.get('image_url','').strip()
    try: price = float(form.get('price',''))
    except ValueError: price = -1
    try: stock = int(form.get('stock',''))
    except ValueError: stock = -1
    errors = []
    if not name: errors.append('Product name is required.')
    if not category: errors.append('Category is required.')
    if price < 0: errors.append('Price must be a valid non-negative number.')
    if stock < 0: errors.append('Stock must be a non-negative whole number.')
    if image_url and not (image_url.startswith('https://') or image_url.startswith('http://')): errors.append('Image URL must start with http:// or https://.')
    return {'name':name,'category':category,'description':description,'price':price,'stock':stock,'image_url':image_url}, errors

@app.route('/admin/products/new', methods=['GET','POST'])
def product_new():
    if request.method == 'POST':
        data, errors = validate_product(request.form)
        if errors:
            for e in errors: flash(e, 'error')
            return render_template('product_form.html', product=data, heading='Add product', action=url_for('product_new'))
        with closing(db()) as con:
            con.execute('INSERT INTO products(name,category,description,price,stock,image_url) VALUES(?,?,?,?,?,?)', (data['name'],data['category'],data['description'],data['price'],data['stock'],data['image_url']))
            con.commit(); con.close()
        flash('Product created successfully.', 'success'); return redirect(url_for('admin_products'))
    return render_template('product_form.html', product={}, heading='Add product', action=url_for('product_new'))

@app.route('/admin/products/<int:product_id>/edit', methods=['GET','POST'])
def product_edit(product_id):
    p = get_product(product_id)
    if not p: abort(404)
    if request.method == 'POST':
        data, errors = validate_product(request.form)
        if errors:
            for e in errors: flash(e, 'error')
            data['id'] = product_id
            return render_template('product_form.html', product=data, heading='Edit product', action=url_for('product_edit', product_id=product_id))
        with closing(db()) as con:
            con.execute('UPDATE products SET name=?,category=?,description=?,price=?,stock=?,image_url=? WHERE id=?', (data['name'],data['category'],data['description'],data['price'],data['stock'],data['image_url'],product_id))
            con.commit(); con.close()
        flash('Product updated successfully.', 'success'); return redirect(url_for('admin_products'))
    return render_template('product_form.html', product=p, heading='Edit product', action=url_for('product_edit', product_id=product_id))

@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
def product_delete(product_id):
    with closing(db()) as con:
        exists = con.execute('SELECT id FROM products WHERE id=?', (product_id,)).fetchone()
        if not exists: con.close(); abort(404)
        con.execute('DELETE FROM products WHERE id=?', (product_id,)); con.commit(); con.close()
    flash('Product deleted successfully.', 'success'); return redirect(url_for('admin_products'))

@app.route('/admin/orders')
def admin_orders():
    with closing(db()) as con:
        orders = con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall(); con.close()
    return render_template('orders.html', orders=orders)

@app.route('/admin/orders/<int:order_id>')
def order_detail(order_id):
    with closing(db()) as con:
        order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order: con.close(); abort(404)
        items = con.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,)).fetchall(); con.close()
    return render_template('order_detail.html', order=order, items=items)

@app.errorhandler(404)
def not_found(_):
    return render_template('404.html'), 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
