import os
from dotenv import load_dotenv
import pyodbc
import uuid
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mi_clave_secreta')

ADMIN_USER = os.environ.get('ADMIN_USER')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

def get_db_connection():
    connection_str = (
        "DRIVER={MySQL ODBC 9.2 ANSI Driver};"
        f"SERVER={os.environ.get('DB_HOST')};"
        "PORT=3306;"
        f"DATABASE={os.environ.get('DB_NAME')};"
        f"USER={os.environ.get('DB_USER')};"
        f"PASSWORD={os.environ.get('DB_PASSWORD')};"
        "OPTION=3;"
    )
    return pyodbc.connect(connection_str)

@app.route('/')
def index():
    if session.get('user_role') == 'admin':
        return redirect(url_for('productos'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('user')
        password = request.form.get('password')
        if user == ADMIN_USER and password == ADMIN_PASSWORD:
            session['user_role'] = 'admin'
            session.setdefault('client_info', {})
            session.setdefault('cart', [])
            flash("Bienvenido, admin", "success")
            return redirect(url_for('productos'))
        else:
            flash("Credenciales inválidas", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/productos')
def productos():
    if session.get('user_role') != 'admin':
        flash("Acceso restringido. Inicia sesión.", "warning")
        return redirect(url_for('login'))
    search = request.args.get('search', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    conn = get_db_connection()
    cursor = conn.cursor()
    if search:
        cursor.execute("SELECT COUNT(*) FROM Products WHERE name LIKE ?", ('%' + search + '%',))
    else:
        cursor.execute("SELECT COUNT(*) FROM Products")
    total_rows = cursor.fetchone()[0]
    if search:
        query = """
            SELECT p.product_id, p.name, p.price, s.*
            FROM Products p
            LEFT JOIN Specs s ON p.spec_id = s.spec_id
            WHERE p.name LIKE ?
            ORDER BY p.product_id
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, ('%' + search + '%', per_page, offset))
    else:
        query = """
            SELECT p.product_id, p.name, p.price, s.*
            FROM Products p
            LEFT JOIN Specs s ON p.spec_id = s.spec_id
            ORDER BY p.product_id
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, (per_page, offset))
    columns = [desc[0] for desc in cursor.description]
    base_cols = 3
    specs_indices = range(base_cols, len(columns))
    productos_final = []
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        product_id = row[0]
        product_name = row[1]
        product_price = row[2]
        specs_parts = []
        for i in specs_indices:
            col_name = columns[i]
            col_value = row[i]
            if col_name.lower() in ('spec_id',):
                continue
            if col_value is not None:
                specs_parts.append(f"{col_name}: {col_value}")
        specs_str = ", ".join(specs_parts)
        productos_final.append((product_id, product_name, product_price, specs_str))
    has_prev = page > 1
    has_next = (page * per_page) < total_rows
    return render_template('productos.html',
                           productos=productos_final,
                           search=search,
                           page=page,
                           has_prev=has_prev,
                           has_next=has_next,
                           total_rows=total_rows)


@app.route('/comprar', methods=['GET', 'POST'])
def comprar():
    if session.get('user_role') != 'admin':
        flash("Acceso restringido. Inicia sesión.", "warning")
        return redirect(url_for('login'))
    session.setdefault('client_info', {})
    session.setdefault('cart', [])
    
    if request.method == 'POST':
        if 'save_client' in request.form:
            session['client_info'] = {
                'name': request.form.get('client_name'),
                'phone': request.form.get('client_phone'),
                'email': request.form.get('client_email'),
                'address': request.form.get('client_address')
            }
            flash("Datos del cliente guardados.", "success")
            return redirect(url_for('comprar', search=request.args.get('search', '')))
        elif 'add_product' in request.form:
            product_id = request.form.get('product_id')
            quantity = int(request.form.get('quantity', 0))
            search = request.args.get('search', '')
            if quantity > 0:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT product_id, name, price FROM Products WHERE product_id = ?", (product_id,))
                product = cursor.fetchone()
                if product:
                    session['cart'].append({
                        'id': product[0],
                        'name': product[1],
                        'price': product[2],
                        'quantity': quantity
                    })
                    session.modified = True
                    flash(f"Producto {product[1]} agregado al carrito.", "success")
                cursor.close()
                conn.close()
            return redirect(url_for('comprar', search=search))
        elif 'finalizar_compra' in request.form:
            if not session['cart']:
                flash("No hay productos en el carrito.", "warning")
                return redirect(url_for('comprar', search=request.args.get('search', '')))
            client = session['client_info']
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO Clients (name, phone, email, address)
                    VALUES (?, ?, ?, ?)
                """, (client['name'], client['phone'], client['email'], client['address']))
                conn.commit()
                cursor.execute("SELECT LAST_INSERT_ID()")
                client_id = cursor.fetchone()[0]
                
                p_order_id = str(uuid.uuid4())
                for item in session['cart']:
                    product_id = item['id']
                    quantity = item['quantity']
                    total = item['price'] * quantity
                    created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("""
                        INSERT INTO Orders (p_order_id, client_id, product_id, quantity, total, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (p_order_id, client_id, product_id, quantity, total, created_at))
                conn.commit()
                flash("Compra realizada exitosamente.", "success")
                session['cart'] = []
                return redirect(url_for('productos'))
            except Exception as e:
                conn.rollback()
                flash("Error al crear la orden: " + str(e), "danger")
                return redirect(url_for('comprar', search=request.args.get('search', '')))
            finally:
                cursor.close()
                conn.close()
    else:
        search = request.args.get('search', '')
        products = []
        if search:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT product_id, name, price FROM Products WHERE name LIKE ?", ('%' + search + '%',))
            products = cursor.fetchall()
            cursor.close()
            conn.close()
        return render_template('comprar.html',
                               products=products,
                               search=search,
                               cart=session['cart'],
                               client_info=session['client_info'])

@app.route('/eliminar_producto/<int:product_id>')
def eliminar_producto(product_id):
    session['cart'] = [p for p in session['cart'] if p['id'] != product_id]
    session.modified = True
    flash("Producto eliminado del carrito.", "success")
    return redirect(url_for('comprar', search=request.args.get('search', '')))

@app.route('/ordenes')
def ordenes():
    if session.get('user_role') != 'admin':
        flash("Acceso restringido. Inicia sesión.", "warning")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
          o.p_order_id,
          c.name AS client_name,
          o.product_id,
          p.name AS product_name,
          o.quantity,
          o.total,
          o.created_at
        FROM Orders o
        LEFT JOIN Clients c ON o.client_id = c.client_id
        LEFT JOIN Products p ON o.product_id = p.product_id
        ORDER BY o.created_at DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    orders_dict = {}
    for row in rows:
        p_order_id = row[0]
        client_name = row[1]
        product_name = row[3]
        quantity = row[4]
        total = row[5]
        created_at = row[6]
        if p_order_id not in orders_dict:
            orders_dict[p_order_id] = {
                'client_name': client_name,
                'created_at': created_at,
                'items': []
            }
        orders_dict[p_order_id]['items'].append({
            'product_name': product_name,
            'quantity': quantity,
            'total': total
        })
    return render_template('ordenes.html', orders=orders_dict)

@app.route('/logout')
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
