import sqlite3
import os
import re
from datetime import datetime
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'department_store.db')

def get_db_connection():
    """Create and return a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(seed_sample_data=False):
    """
    Initialize database tables and create default admin account.
    Per Section 21: NO sample products, customers, or bills are inserted.
    Products: 0, Customers: 0, Bills: 0, Payments: 0.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # Products table (NO stock fields)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE,
            price REAL NOT NULL,
            unit TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Customers table (Account customers only)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # Bills table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            customer_type TEXT NOT NULL CHECK(customer_type IN ('existing', 'walkin')),
            customer_name TEXT NOT NULL,
            customer_phone TEXT,
            bill_date TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL DEFAULT 0.0,
            grand_total REAL NOT NULL,
            paid_amount REAL NOT NULL DEFAULT 0.0,
            balance REAL NOT NULL DEFAULT 0.0,
            pdf_path TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        )
    ''')

    # Bill items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
    ''')

    # Payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            bill_id INTEGER,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()

    # Seed default admin if missing (admin / admin123)
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            ('admin', hashed_pw, now_str)
        )
        conn.commit()

    conn.close()

# ==================== USER FUNCTIONS ====================

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

# ==================== PRODUCT FUNCTIONS ====================

def get_all_products(search_query=None):
    conn = get_db_connection()
    if search_query:
        query = "%" + search_query.strip() + "%"
        products = conn.execute(
            "SELECT * FROM products WHERE name LIKE ? ORDER BY name ASC",
            (query,)
        ).fetchall()
    else:
        products = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return product

def get_product_by_name(name):
    """Case-insensitive lookup to check duplicate product names."""
    conn = get_db_connection()
    product = conn.execute(
        "SELECT * FROM products WHERE LOWER(name) = LOWER(?)",
        (name.strip(),)
    ).fetchone()
    conn.close()
    return product

def add_product(name, price, unit):
    """
    Add product with validation.
    Enforces uniqueness: if product with same name already exists, raises ValueError.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Product name is required.")

    try:
        clean_price = round(float(price), 2)
        if clean_price <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Product price must be a number greater than 0.")

    clean_unit = unit.strip()
    if not clean_unit:
        raise ValueError("Unit is required (e.g. 1kg, 5kg, 1L, piece).")

    # Check for existing product with the same name
    existing = get_product_by_name(clean_name)
    if existing:
        raise ValueError("Product already exists. Please use the existing product or edit its price.")

    conn = get_db_connection()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, price, unit, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (clean_name, clean_price, clean_unit, now_str, now_str)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def update_product(product_id, name, price, unit):
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Product name is required.")

    try:
        clean_price = round(float(price), 2)
        if clean_price <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Product price must be a number greater than 0.")

    clean_unit = unit.strip()
    if not clean_unit:
        raise ValueError("Unit is required.")

    # Check duplicate name with another product
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT id FROM products WHERE LOWER(name) = LOWER(?) AND id != ?",
        (clean_name, product_id)
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError("Another product with this name already exists.")

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "UPDATE products SET name = ?, price = ?, unit = ?, updated_at = ? WHERE id = ?",
        (clean_name, clean_price, clean_unit, now_str, product_id)
    )
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

# ==================== CUSTOMER FUNCTIONS ====================

def get_all_customers(search_query=None):
    """Return all account customers with dynamically calculated financial summaries."""
    conn = get_db_connection()
    if search_query:
        query = "%" + search_query.strip() + "%"
        customers = conn.execute(
            "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name ASC",
            (query, query)
        ).fetchall()
    else:
        customers = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()

    customer_list = []
    for c in customers:
        fin = get_customer_financial_summary(c['id'], conn)
        c_dict = dict(c)
        c_dict['total_purchases'] = fin['total_purchases']
        c_dict['total_paid'] = fin['total_paid']
        c_dict['outstanding_balance'] = fin['outstanding_balance']
        c_dict['total_bills'] = fin['total_bills']
        customer_list.append(c_dict)

    conn.close()
    return customer_list

def get_customer_by_id(customer_id):
    conn = get_db_connection()
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()
    return customer

def add_customer(name, phone='', address=''):
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Customer name is required.")

    clean_phone = phone.strip() if phone else ''
    if clean_phone and not re.match(r'^[0-9+\-\s()]{7,15}$', clean_phone):
        raise ValueError("Please enter a valid phone number (digits and optional + or -).")

    conn = get_db_connection()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO customers (name, phone, address, created_at) VALUES (?, ?, ?, ?)",
        (clean_name, clean_phone, address.strip() if address else '', now_str)
    )
    customer_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return customer_id

def update_customer(customer_id, name, phone='', address=''):
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Customer name is required.")

    clean_phone = phone.strip() if phone else ''
    if clean_phone and not re.match(r'^[0-9+\-\s()]{7,15}$', clean_phone):
        raise ValueError("Please enter a valid phone number.")

    conn = get_db_connection()
    conn.execute(
        "UPDATE customers SET name = ?, phone = ?, address = ? WHERE id = ?",
        (clean_name, clean_phone, address.strip() if address else '', customer_id)
    )
    conn.commit()
    conn.close()

def delete_customer(customer_id):
    """Deleting a customer only deletes their record and cascades where applicable."""
    conn = get_db_connection()
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()

def get_customer_financial_summary(customer_id, conn=None):
    """
    CRITICAL ACCOUNT RULE (Section 18 & 19):
    Calculate customer outstanding balance from:
    Total Grand Total of account customer's bills
    minus
    Total payments made by that customer.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    # Total purchases = sum of grand_total of bills for this customer
    res_bills = conn.execute(
        "SELECT COUNT(*) as bill_count, COALESCE(SUM(grand_total), 0.0) as total_purchases FROM bills WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()

    # Total paid = sum of all payments made by this customer
    res_payments = conn.execute(
        "SELECT COALESCE(SUM(amount), 0.0) as total_paid FROM payments WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()

    total_purchases = round(float(res_bills['total_purchases']), 2)
    total_paid = round(float(res_payments['total_paid']), 2)
    outstanding_balance = round(total_purchases - total_paid, 2)
    if abs(outstanding_balance) < 0.001:
        outstanding_balance = 0.0

    if should_close:
        conn.close()

    return {
        'total_bills': res_bills['bill_count'],
        'total_purchases': total_purchases,
        'total_paid': total_paid,
        'outstanding_balance': max(0.0, outstanding_balance)
    }

def get_customer_bills(customer_id, month=None, year=None):
    conn = get_db_connection()
    sql = "SELECT * FROM bills WHERE customer_id = ?"
    params = [customer_id]

    if year:
        sql += " AND strftime('%Y', bill_date) = ?"
        params.append(str(year).zfill(4))
    if month:
        sql += " AND strftime('%m', bill_date) = ?"
        params.append(str(month).zfill(2))

    sql += " ORDER BY bill_date DESC, id DESC"
    bills = conn.execute(sql, params).fetchall()
    conn.close()
    return bills

def get_customer_monthly_history(customer_id, selected_year=None, selected_month=None):
    """
    Return monthly history data for the customer account page.

    When a specific year+month is selected, also computes:
      - previous_pending  : unpaid balance from all months BEFORE selected month
      - payments_this_month : total payments recorded in the selected month
      - grand_total       : previous_pending + current_month purchases
      - amount_payable    : grand_total - payments_this_month  (>= 0)

    This ensures the web page and PDF always use the same calculation logic.
    """
    conn = get_db_connection()
    bills = get_customer_bills(customer_id, month=selected_month, year=selected_year)

    # Current month purchases = sum of grand_totals for the filtered bills
    monthly_total = round(sum(float(b['grand_total']) for b in bills), 2)

    # payments_this_month: actual payment records in the selected period
    if selected_year and selected_month:
        month_prefix = '{:04d}-{:02d}'.format(int(selected_year), int(selected_month))
        pm_row = conn.execute('''
            SELECT COALESCE(SUM(amount), 0.0) AS total
            FROM payments
            WHERE customer_id = ?
              AND strftime('%Y-%m', payment_date) = ?
        ''', (customer_id, month_prefix)).fetchone()
        payments_this_month = round(float(pm_row['total']), 2)

        # Previous pending = purchases before cutoff - payments before cutoff
        cutoff_date = '{:04d}-{:02d}-01'.format(int(selected_year), int(selected_month))
        prev_pur = conn.execute('''
            SELECT COALESCE(SUM(grand_total), 0.0) AS total
            FROM bills WHERE customer_id = ? AND bill_date < ?
        ''', (customer_id, cutoff_date)).fetchone()
        prev_pay = conn.execute('''
            SELECT COALESCE(SUM(amount), 0.0) AS total
            FROM payments WHERE customer_id = ? AND payment_date < ?
        ''', (customer_id, cutoff_date)).fetchone()
        previous_pending = max(0.0, round(float(prev_pur['total']) - float(prev_pay['total']), 2))
    else:
        # No month filter: previous_pending and payments_this_month not applicable
        payments_this_month = round(sum(
            float(b['paid_amount']) for b in bills
        ), 2)
        previous_pending = 0.0

    grand_total    = round(previous_pending + monthly_total, 2)
    amount_payable = max(0.0, round(grand_total - payments_this_month, 2))
    # Legacy field kept for template compatibility
    monthly_balance = amount_payable

    available_dates = conn.execute(
        "SELECT DISTINCT strftime('%Y', bill_date) as year, strftime('%m', bill_date) as month "
        "FROM bills WHERE customer_id = ? ORDER BY year DESC, month DESC",
        (customer_id,)
    ).fetchall()

    conn.close()
    return {
        'bills':               bills,
        'monthly_total':       monthly_total,
        'monthly_paid':        payments_this_month,
        'monthly_balance':     monthly_balance,
        'previous_pending':    previous_pending,
        'grand_total':         grand_total,
        'amount_payable':      amount_payable,
        'available_dates':     available_dates,
        'is_filtered':         bool(selected_year and selected_month),
    }

def get_customer_payments(customer_id):
    conn = get_db_connection()
    payments = conn.execute('''
        SELECT p.*, b.bill_number 
        FROM payments p 
        LEFT JOIN bills b ON p.bill_id = b.id 
        WHERE p.customer_id = ? 
        ORDER BY p.payment_date DESC, p.id DESC
    ''', (customer_id,)).fetchall()
    conn.close()
    return payments

# ==================== PAYMENT FUNCTIONS ====================

def add_payment(customer_id, amount, payment_date=None, bill_id=None, notes=''):
    conn = get_db_connection()
    fin = get_customer_financial_summary(customer_id, conn)
    current_balance = fin['outstanding_balance']

    amount = round(float(amount), 2)
    if amount <= 0:
        conn.close()
        raise ValueError("Payment amount must be greater than zero.")

    if amount > (current_balance + 0.01):
        conn.close()
        raise ValueError(f"Payment amount (₹{amount:.2f}) cannot exceed customer's outstanding balance (₹{current_balance:.2f}).")

    if not payment_date:
        payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO payments (customer_id, bill_id, amount, payment_date, notes) VALUES (?, ?, ?, ?, ?)",
        (customer_id, bill_id, amount, payment_date, notes.strip() if notes else 'Account Settlement')
    )
    payment_id = cursor.lastrowid

    if bill_id:
        bill = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
        if bill:
            new_bill_paid = min(round(bill['grand_total'], 2), round(bill['paid_amount'] + amount, 2))
            new_bill_bal = max(0.0, round(bill['grand_total'] - new_bill_paid, 2))
            conn.execute("UPDATE bills SET paid_amount = ?, balance = ? WHERE id = ?", (new_bill_paid, new_bill_bal, bill_id))

    conn.commit()
    conn.close()
    return payment_id

# ==================== BILL FUNCTIONS ====================

def generate_next_bill_number():
    conn = get_db_connection()
    last_bill = conn.execute("SELECT id, bill_number FROM bills ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    if not last_bill:
        return "BILL-1001"
    
    bill_num_str = last_bill['bill_number']
    if '-' in bill_num_str:
        try:
            num = int(bill_num_str.split('-')[1])
            return f"BILL-{num + 1}"
        except (ValueError, IndexError):
            pass
    return f"BILL-{1000 + last_bill['id'] + 1}"

def create_bill(customer_type, customer_id, customer_name, customer_phone, items, discount=0.0, paid_amount=0.0, bill_date=None):
    if not items or len(items) == 0:
        raise ValueError("Cannot create an empty bill. Please add at least one product.")

    if not bill_date:
        bill_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        discount = max(0.0, round(float(discount), 2))
    except (ValueError, TypeError):
        discount = 0.0

    try:
        paid_amount = max(0.0, round(float(paid_amount), 2))
    except (ValueError, TypeError):
        paid_amount = 0.0

    subtotal = 0.0
    validated_items = []
    for item in items:
        qty = float(item['quantity'])
        price = float(item['price'])
        if qty <= 0:
            raise ValueError(f"Quantity must be greater than zero for product '{item.get('product_name', '')}'.")
        if price < 0:
            raise ValueError(f"Price cannot be negative for product '{item.get('product_name', '')}'.")
        
        item_total = round(qty * price, 2)
        subtotal += item_total
        validated_items.append({
            'product_id': item.get('product_id'),
            'product_name': item['product_name'].strip(),
            'quantity': qty,
            'price': price,
            'total': item_total
        })

    subtotal = round(subtotal, 2)
    if discount > subtotal:
        discount = subtotal
    grand_total = round(subtotal - discount, 2)

    if paid_amount > (grand_total + 0.001):
        raise ValueError(f"Paid amount (₹{paid_amount:.2f}) cannot be greater than grand total (₹{grand_total:.2f}).")

    balance = max(0.0, round(grand_total - paid_amount, 2))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        bill_number = generate_next_bill_number()

        if customer_type == 'existing':
            if not customer_id:
                raise ValueError("An existing account customer must be selected.")
            cust = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not cust:
                raise ValueError(f"Customer with ID {customer_id} does not exist.")
            actual_customer_id = cust['id']
            actual_customer_name = cust['name']
            actual_customer_phone = cust['phone']
        else:
            # Walk-in customer: DO NOT create an account in customers table
            actual_customer_id = None
            customer_type = 'walkin'
            clean_walkin_name = customer_name.strip() if customer_name else ''
            if not clean_walkin_name:
                raise ValueError("Customer name is required for walk-in customer.")
            actual_customer_name = clean_walkin_name
            actual_customer_phone = customer_phone.strip() if customer_phone else ''

        cursor.execute('''
            INSERT INTO bills (
                bill_number, customer_id, customer_type, customer_name, customer_phone,
                bill_date, subtotal, discount, grand_total, paid_amount, balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bill_number, actual_customer_id, customer_type, actual_customer_name, actual_customer_phone,
            bill_date, subtotal, discount, grand_total, paid_amount, balance
        ))
        bill_id = cursor.lastrowid

        for vi in validated_items:
            cursor.execute('''
                INSERT INTO bill_items (bill_id, product_id, product_name, quantity, price, total)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (bill_id, vi['product_id'], vi['product_name'], vi['quantity'], vi['price'], vi['total']))

        if actual_customer_id and paid_amount > 0:
            cursor.execute('''
                INSERT INTO payments (customer_id, bill_id, amount, payment_date, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (actual_customer_id, bill_id, paid_amount, bill_date, f'Payment at billing for {bill_number}'))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e

    conn.close()
    return bill_id

def get_bill_by_id(bill_id):
    conn = get_db_connection()
    bill = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    conn.close()
    return bill

def get_bill_by_number(bill_number):
    conn = get_db_connection()
    bill = conn.execute("SELECT * FROM bills WHERE bill_number = ?", (bill_number,)).fetchone()
    conn.close()
    return bill

def get_bill_items(bill_id):
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,)).fetchall()
    conn.close()
    return items

def update_bill_pdf_path(bill_id, pdf_path):
    conn = get_db_connection()
    conn.execute("UPDATE bills SET pdf_path = ? WHERE id = ?", (pdf_path, bill_id))
    conn.commit()
    conn.close()

def has_bill_payments(bill_id):
    """Check how many payments are associated with this bill."""
    conn = get_db_connection()
    res = conn.execute("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0.0) as total_amount FROM payments WHERE bill_id = ?", (bill_id,)).fetchone()
    conn.close()
    return {'count': res['count'], 'total_amount': round(float(res['total_amount']), 2)}

def delete_bill(bill_id, invoices_folder=None):
    """
    CRITICAL REQUIREMENT (Section 3, 4, 5, 6, 7):
    Delete an incorrect bill inside a strict ACID transaction.
    1. Delete all bill_items belonging to that bill
    2. Delete related payments belonging to that bill
    3. Delete the bill record
    4. Delete generated PDF invoice from invoices folder if present
    5. Recalculates customer balance (done dynamically via formula)
    6. Does NEVER delete the customer
    7. Does NEVER delete the product
    """
    conn = get_db_connection()
    bill = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if not bill:
        conn.close()
        raise ValueError(f"Bill with ID {bill_id} not found.")

    cursor = conn.cursor()
    try:
        # 1. Delete associated payments
        cursor.execute("DELETE FROM payments WHERE bill_id = ?", (bill_id,))
        # 2. Delete bill items
        cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (bill_id,))
        # 3. Delete bill
        cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise Exception(f"Unable to delete bill: {str(e)}")

    conn.close()

    # 4. Remove physical PDF file if it exists
    if invoices_folder:
        pdf_file = os.path.join(invoices_folder, f"{bill['bill_number']}.pdf")
        if os.path.exists(pdf_file):
            try:
                os.remove(pdf_file)
            except Exception:
                pass

    return bill

def get_all_bills(search_query=None, filter_period='all', from_date=None, to_date=None):
    conn = get_db_connection()
    sql = "SELECT * FROM bills WHERE 1=1"
    params = []

    if search_query:
        q = "%" + search_query.strip() + "%"
        sql += " AND (bill_number LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?)"
        params.extend([q, q, q])

    if filter_period == 'today':
        sql += " AND date(bill_date) = date('now', 'localtime')"
    elif filter_period == 'week':
        sql += " AND date(bill_date) >= date('now', 'localtime', '-7 days')"
    elif filter_period == 'month':
        sql += " AND strftime('%Y-%m', bill_date) = strftime('%Y-%m', 'now', 'localtime')"
    elif filter_period == 'custom' and from_date and to_date:
        sql += " AND date(bill_date) BETWEEN date(?) AND date(?)"
        params.extend([from_date, to_date])

    sql += " ORDER BY bill_date DESC, id DESC"
    bills = conn.execute(sql, params).fetchall()
    conn.close()
    return bills

def get_recent_bills(limit=8):
    conn = get_db_connection()
    bills = conn.execute("SELECT * FROM bills ORDER BY bill_date DESC, id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return bills

# ==================== DASHBOARD & REPORTS ====================

def get_dashboard_stats():
    conn = get_db_connection()

    today_res = conn.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(grand_total), 0.0) as sales
        FROM bills 
        WHERE date(bill_date) = date('now', 'localtime')
    ''').fetchone()

    month_res = conn.execute('''
        SELECT COALESCE(SUM(grand_total), 0.0) as sales
        FROM bills 
        WHERE strftime('%Y-%m', bill_date) = strftime('%Y-%m', 'now', 'localtime')
    ''').fetchone()

    cust_res = conn.execute("SELECT COUNT(*) as count FROM customers").fetchone()

    purchases_res = conn.execute('''
        SELECT COALESCE(SUM(grand_total), 0.0) as total_purchases
        FROM bills
        WHERE customer_id IS NOT NULL
    ''').fetchone()

    payments_res = conn.execute('''
        SELECT COALESCE(SUM(amount), 0.0) as total_payments
        FROM payments
    ''').fetchone()

    tot_purchases = float(purchases_res['total_purchases'])
    tot_payments = float(payments_res['total_payments'])
    total_outstanding = max(0.0, round(tot_purchases - tot_payments, 2))

    conn.close()

    return {
        'today_sales': round(float(today_res['sales']), 2),
        'today_bills': today_res['count'],
        'monthly_sales': round(float(month_res['sales']), 2),
        'total_customers': cust_res['count'],
        'total_outstanding_balance': total_outstanding
    }

def get_sales_report_data():
    conn = get_db_connection()

    monthly_trend = conn.execute('''
        SELECT 
            strftime('%Y-%m', bill_date) as month_str,
            COUNT(*) as bill_count,
            COALESCE(SUM(grand_total), 0.0) as total_sales,
            COALESCE(SUM(paid_amount), 0.0) as total_collected
        FROM bills
        GROUP BY strftime('%Y-%m', bill_date)
        ORDER BY month_str DESC
        LIMIT 12
    ''').fetchall()

    customers = conn.execute("SELECT id, name, phone FROM customers").fetchall()
    customer_balances = []
    for c in customers:
        fin = get_customer_financial_summary(c['id'], conn)
        if fin['outstanding_balance'] > 0:
            customer_balances.append({
                'id': c['id'],
                'name': c['name'],
                'phone': c['phone'],
                'total_purchases': fin['total_purchases'],
                'total_paid': fin['total_paid'],
                'outstanding_balance': fin['outstanding_balance']
            })
    customer_balances.sort(key=lambda x: x['outstanding_balance'], reverse=True)

    conn.close()
    return {
        'monthly_trend': monthly_trend,
        'customer_balances': customer_balances
    }


# ==================== SHOP SETTINGS FUNCTIONS ====================

def init_settings_table(conn=None):
    """Create shop_settings table if not exists and seed defaults."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shop_settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL
        )
    ''')
    defaults = [
        ('shop_name',    'FRUITS SHOP'),
        ('shop_address', '123 Market Street, Town'),
        ('shop_phone',   '+91 98765 43210'),
        ('shop_email',   ''),
        ('shop_gst',     ''),
    ]
    for key, value in defaults:
        conn.execute(
            'INSERT OR IGNORE INTO shop_settings (key, value) VALUES (?, ?)',
            (key, value)
        )
    conn.commit()
    if should_close:
        conn.close()

def get_shop_settings():
    """Return all shop settings as a plain dict."""
    conn = get_db_connection()
    init_settings_table(conn)
    rows = conn.execute('SELECT key, value FROM shop_settings').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def update_shop_settings(settings_dict):
    """Upsert multiple settings at once from a dict."""
    conn = get_db_connection()
    init_settings_table(conn)
    for key, value in settings_dict.items():
        conn.execute(
            'INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?, ?)',
            (key, str(value).strip())
        )
    conn.commit()
    conn.close()

# ==================== MONTHLY BILL / STATEMENT FUNCTIONS ====================

def get_monthly_bill_data(customer_id, year, month):
    """
    Build complete monthly statement data for an account customer.

    Returns a dict with:
      customer            - customer row as dict
      year, month         - ints
      month_name          - e.g. 'September'
      transactions        - list of dicts (one per bill = one date group):
                              { bill_id, bill_number, bill_date, date_str,
                                items: [{product_name, quantity, total}],
                                bill_total }
      current_total       - sum of grand_total of bills in selected month
      previous_pending    - unpaid balance from ALL months BEFORE selected month
      payments_this_month - total payments recorded in this month
      grand_total         - previous_pending + current_total
      amount_payable      - grand_total - payments_this_month (>= 0)
      has_transactions    - bool
    """
    conn = get_db_connection()

    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    if not customer:
        conn.close()
        raise ValueError('Customer not found.')

    year  = int(year)
    month = int(month)
    month_prefix = '{:04d}-{:02d}'.format(year, month)
    cutoff_date  = '{:04d}-{:02d}-01'.format(year, month)

    # Bills in the selected month
    bills_this_month = conn.execute('''
        SELECT * FROM bills
        WHERE customer_id = ?
          AND strftime('%Y-%m', bill_date) = ?
        ORDER BY bill_date ASC, id ASC
    ''', (customer_id, month_prefix)).fetchall()

    current_total = round(sum(float(b['grand_total']) for b in bills_this_month), 2)

    # Build grouped transaction rows
    transactions = []
    for b in bills_this_month:
        items = conn.execute(
            'SELECT * FROM bill_items WHERE bill_id = ? ORDER BY id ASC',
            (b['id'],)
        ).fetchall()
        raw_date = b['bill_date'][:10]
        try:
            dt = datetime.strptime(raw_date, '%Y-%m-%d')
            date_str = dt.strftime('%d/%m/%Y')
        except Exception:
            date_str = raw_date

        transactions.append({
            'bill_id':     b['id'],
            'bill_number': b['bill_number'],
            'bill_date':   b['bill_date'],
            'date_str':    date_str,
            'items': [
                {
                    'product_name': it['product_name'],
                    'quantity':     it['quantity'],
                    'price':        float(it['price']),
                    'total':        float(it['total']),
                }
                for it in items
            ],
            'bill_total': float(b['grand_total']),
        })

    # Payments in the selected month
    payments_row = conn.execute('''
        SELECT COALESCE(SUM(amount), 0.0) AS total
        FROM payments
        WHERE customer_id = ?
          AND strftime('%Y-%m', payment_date) = ?
    ''', (customer_id, month_prefix)).fetchone()
    payments_this_month = round(float(payments_row['total']), 2)

    # Previous pending = all purchases before cutoff - all payments before cutoff
    prev_pur_row = conn.execute('''
        SELECT COALESCE(SUM(grand_total), 0.0) AS total
        FROM bills
        WHERE customer_id = ? AND bill_date < ?
    ''', (customer_id, cutoff_date)).fetchone()
    prev_pay_row = conn.execute('''
        SELECT COALESCE(SUM(amount), 0.0) AS total
        FROM payments
        WHERE customer_id = ? AND payment_date < ?
    ''', (customer_id, cutoff_date)).fetchone()

    previous_pending = max(0.0, round(float(prev_pur_row['total']) - float(prev_pay_row['total']), 2))

    grand_total    = round(previous_pending + current_total, 2)
    amount_payable = max(0.0, round(grand_total - payments_this_month, 2))

    conn.close()

    return {
        'customer':            dict(customer),
        'year':                year,
        'month':               month,
        'month_name':          datetime(year, month, 1).strftime('%B'),
        'transactions':        transactions,
        'current_total':       current_total,
        'previous_pending':    previous_pending,
        'payments_this_month': payments_this_month,
        'grand_total':         grand_total,
        'amount_payable':      amount_payable,
        'has_transactions':    len(transactions) > 0,
    }


def get_customer_monthly_summary_list(customer_id):
    """
    Return a list of month summaries for which the customer has bills.
    Used to build the Account History section on the customer details page.
    """
    conn = get_db_connection()
    months_rows = conn.execute('''
        SELECT DISTINCT
            CAST(strftime('%Y', bill_date) AS INTEGER) AS year,
            CAST(strftime('%m', bill_date) AS INTEGER) AS month
        FROM bills
        WHERE customer_id = ?
        ORDER BY year DESC, month DESC
    ''', (customer_id,)).fetchall()
    conn.close()

    results = []
    for row in months_rows:
        y, m = row['year'], row['month']
        try:
            data = get_monthly_bill_data(customer_id, y, m)
            results.append({
                'year':            y,
                'month':           m,
                'month_name':      data['month_name'],
                'current_total':   data['current_total'],
                'payments':        data['payments_this_month'],
                'closing_balance': data['amount_payable'],
            })
        except Exception:
            pass

    return results


def get_monthly_bill_data_alltime(customer_id):
    """
    Build a complete all-time account statement for a customer.
    Used when 'All Years / All Months' is selected and the user downloads the full statement.
    """
    conn = get_db_connection()
    customer = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    if not customer:
        conn.close()
        raise ValueError('Customer not found.')

    all_bills = conn.execute('''
        SELECT * FROM bills WHERE customer_id = ? ORDER BY bill_date ASC, id ASC
    ''', (customer_id,)).fetchall()

    transactions = []
    for b in all_bills:
        items = conn.execute(
            'SELECT * FROM bill_items WHERE bill_id = ? ORDER BY id ASC', (b['id'],)
        ).fetchall()
        raw_date = b['bill_date'][:10]
        try:
            dt = datetime.strptime(raw_date, '%Y-%m-%d')
            date_str = dt.strftime('%d/%m/%Y')
        except Exception:
            date_str = raw_date
        transactions.append({
            'bill_id':     b['id'],
            'bill_number': b['bill_number'],
            'bill_date':   b['bill_date'],
            'date_str':    date_str,
            'items': [
                {
                    'product_name': it['product_name'],
                    'quantity':     it['quantity'],
                    'price':        float(it['price']),
                    'total':        float(it['total']),
                }
                for it in items
            ],
            'bill_total': float(b['grand_total']),
        })

    total_purchases_row = conn.execute(
        'SELECT COALESCE(SUM(grand_total), 0.0) AS t FROM bills WHERE customer_id = ?',
        (customer_id,)
    ).fetchone()
    total_payments_row = conn.execute(
        'SELECT COALESCE(SUM(amount), 0.0) AS t FROM payments WHERE customer_id = ?',
        (customer_id,)
    ).fetchone()

    current_total       = round(float(total_purchases_row['t']), 2)
    payments_this_month = round(float(total_payments_row['t']), 2)
    previous_pending    = 0.0
    grand_total         = current_total
    amount_payable      = max(0.0, round(grand_total - payments_this_month, 2))

    conn.close()
    return {
        'customer':            dict(customer),
        'year':                None,
        'month':               None,
        'month_name':          'All Time',
        'transactions':        transactions,
        'current_total':       current_total,
        'previous_pending':    previous_pending,
        'payments_this_month': payments_this_month,
        'grand_total':         grand_total,
        'amount_payable':      amount_payable,
        'has_transactions':    len(transactions) > 0,
        'is_alltime':          True,
    }
