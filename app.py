import os
import logging
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, abort
)
from werkzeug.security import check_password_hash
import database
import pdf_generator
import monthly_pdf

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dept_store_super_secret_key_2026')
app.config['INVOICES_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoices')
os.makedirs(app.config['INVOICES_FOLDER'], exist_ok=True)

# Initialize database on startup (Zero sample data)
database.init_db(seed_sample_data=False)
database.init_settings_table()   # Create shop_settings table + seed defaults

# ----------------- Auth Decorator -----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- Context Processor -----------------

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

# ----------------- Auth Routes -----------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html')

        try:
            user = database.get_user_by_username(username)
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash(f"Welcome back, {user['username']}!", 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password. Please try again.', 'danger')
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            flash('Unable to process login at this time. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ----------------- Dashboard -----------------

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        stats = database.get_dashboard_stats()
        recent_bills = database.get_recent_bills(limit=8)
        return render_template('dashboard.html', stats=stats, recent_bills=recent_bills)
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        flash('Unable to load dashboard statistics.', 'danger')
        return render_template('dashboard.html', stats={
            'today_sales': 0.0, 'today_bills': 0, 'monthly_sales': 0.0,
            'total_customers': 0, 'total_outstanding_balance': 0.0
        }, recent_bills=[])

# ----------------- Product Management -----------------

@app.route('/products')
@login_required
def products():
    search_query = request.args.get('search', '').strip()
    try:
        products_list = database.get_all_products(search_query=search_query if search_query else None)
        return render_template('products.html', products=products_list, search_query=search_query)
    except Exception as e:
        logger.error(f"Products listing error: {e}", exc_info=True)
        flash('Unable to load products. Please try again.', 'danger')
        return render_template('products.html', products=[], search_query=search_query)

@app.route('/products/add', methods=['POST'])
@login_required
def add_product():
    name = request.form.get('name', '').strip()
    price_str = request.form.get('price', '').strip()
    unit = request.form.get('unit', '').strip()

    try:
        database.add_product(name, price_str, unit)
        flash(f"Product '{name}' added successfully.", 'success')
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        logger.error(f"Add product error: {e}", exc_info=True)
        flash('Unable to save product. Please check the entered information and try again.', 'danger')

    return redirect(url_for('products'))

@app.route('/products/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """
    CRITICAL REQUIREMENT (Section 1 & 2):
    Add product directly from Create Bill page via AJAX without full page refresh.
    Returns JSON { success, product: { id, name, price, unit } }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'Invalid product data provided.'}), 400

        name = data.get('name', '').strip()
        price = data.get('price')
        unit = data.get('unit', '').strip()

        product_id = database.add_product(name, price, unit)
        p = database.get_product_by_id(product_id)

        return jsonify({
            'success': True,
            'message': f"Product '{p['name']}' added successfully!",
            'product': {
                'id': p['id'],
                'name': p['name'],
                'price': float(p['price']),
                'unit': p['unit']
            }
        })
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"Quick add product error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Unable to save the product. Please try again.'}), 500

@app.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
def edit_product(product_id):
    name = request.form.get('name', '').strip()
    price_str = request.form.get('price', '').strip()
    unit = request.form.get('unit', '').strip()

    try:
        database.update_product(product_id, name, price_str, unit)
        flash(f"Product '{name}' updated successfully! New price will apply to future bills.", 'success')
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        logger.error(f"Edit product error: {e}", exc_info=True)
        flash('Unable to update product. Please check the entered information and try again.', 'danger')

    return redirect(url_for('products'))

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    try:
        product = database.get_product_by_id(product_id)
        if product:
            database.delete_product(product_id)
            flash(f"Product '{product['name']}' deleted.", 'info')
        else:
            flash('Product not found.', 'warning')
    except Exception as e:
        logger.error(f"Delete product error: {e}", exc_info=True)
        flash('Unable to delete product.', 'danger')
    return redirect(url_for('products'))

# ----------------- Customer Management -----------------

@app.route('/customers')
@login_required
def customers():
    search_query = request.args.get('search', '').strip()
    try:
        customers_list = database.get_all_customers(search_query=search_query if search_query else None)
        return render_template('customers.html', customers=customers_list, search_query=search_query)
    except Exception as e:
        logger.error(f"Customers listing error: {e}", exc_info=True)
        flash('Unable to load customers.', 'danger')
        return render_template('customers.html', customers=[], search_query=search_query)

@app.route('/customers/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    try:
        database.add_customer(name, phone, address)
        flash(f"Account Customer '{name}' created successfully.", 'success')
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        logger.error(f"Add customer error: {e}", exc_info=True)
        flash('Unable to create customer account. Please try again.', 'danger')

    return redirect(url_for('customers'))

@app.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
def edit_customer(customer_id):
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    try:
        database.update_customer(customer_id, name, phone, address)
        flash(f"Customer '{name}' updated successfully.", 'success')
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        logger.error(f"Edit customer error: {e}", exc_info=True)
        flash('Unable to update customer information.', 'danger')

    return redirect(url_for('customer_details', customer_id=customer_id))

@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    try:
        cust = database.get_customer_by_id(customer_id)
        if cust:
            database.delete_customer(customer_id)
            flash(f"Customer '{cust['name']}' deleted.", 'info')
        else:
            flash('Customer not found.', 'warning')
    except Exception as e:
        logger.error(f"Delete customer error: {e}", exc_info=True)
        flash('Unable to delete customer account.', 'danger')
    return redirect(url_for('customers'))

@app.route('/customers/<int:customer_id>')
@login_required
def customer_details(customer_id):
    cust = database.get_customer_by_id(customer_id)
    if not cust:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers'))

    financials = database.get_customer_financial_summary(customer_id)
    selected_year = request.args.get('year')
    selected_month = request.args.get('month')
    monthly_data = database.get_customer_monthly_history(customer_id, selected_year, selected_month)
    payments = database.get_customer_payments(customer_id)

    return render_template(
        'customer_details.html',
        customer=cust,
        financials=financials,
        monthly_data=monthly_data,
        payments=payments,
        selected_year=selected_year,
        selected_month=selected_month
    )

@app.route('/customers/<int:customer_id>/payment', methods=['POST'])
@login_required
def record_payment(customer_id):
    cust = database.get_customer_by_id(customer_id)
    if not cust:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers'))

    amount_str = request.form.get('amount', '').strip()
    payment_date = request.form.get('payment_date', '').strip()
    notes = request.form.get('notes', '').strip()

    try:
        amount = float(amount_str)
        database.add_payment(customer_id, amount, payment_date=payment_date if payment_date else None, notes=notes)
        flash(f"Payment of ₹{amount:.2f} recorded successfully for {cust['name']}.", 'success')
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        logger.error(f"Payment error: {e}", exc_info=True)
        flash('Unable to record payment. Please check the amount and try again.', 'danger')

    return redirect(url_for('customer_details', customer_id=customer_id))

# ----------------- Create Bill Page -----------------

@app.route('/billing')
@login_required
def billing():
    try:
        customers_list = database.get_all_customers()
        products_list = database.get_all_products()
        return render_template('billing.html', customers=customers_list, products=products_list)
    except Exception as e:
        logger.error(f"Billing page error: {e}", exc_info=True)
        flash('Error loading billing catalogue.', 'danger')
        return render_template('billing.html', customers=[], products=[])

@app.route('/billing/save', methods=['POST'])
@login_required
def save_bill():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'Invalid bill data submitted.'}), 400

        customer_type = data.get('customer_type', 'existing')
        customer_id = data.get('customer_id')
        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        items = data.get('items', [])
        discount = float(data.get('discount', 0.0) or 0.0)
        paid_amount = float(data.get('paid_amount', 0.0) or 0.0)
        bill_date = data.get('bill_date')

        if not items:
            return jsonify({'success': False, 'message': 'Bill must contain at least one product.'}), 400

        if customer_type == 'existing' and not customer_id:
            return jsonify({'success': False, 'message': 'Please select an existing account customer.'}), 400

        if customer_type == 'walkin' and not customer_name:
            customer_name = 'Walk-in Customer'

        bill_id = database.create_bill(
            customer_type=customer_type,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            items=items,
            discount=discount,
            paid_amount=paid_amount,
            bill_date=bill_date
        )

        bill = database.get_bill_by_id(bill_id)
        bill_items = database.get_bill_items(bill_id)

        try:
            pdf_path = pdf_generator.generate_pdf_invoice(bill, bill_items, app.config['INVOICES_FOLDER'])
            database.update_bill_pdf_path(bill_id, pdf_path)
        except Exception as pdf_err:
            logger.error(f"PDF generation failed: {pdf_err}", exc_info=True)

        return jsonify({
            'success': True,
            'message': f"Bill {bill['bill_number']} generated successfully!",
            'bill_id': bill_id,
            'bill_number': bill['bill_number'],
            'download_url': url_for('download_pdf', bill_id=bill_id),
            'view_url': url_for('view_bill', bill_id=bill_id)
        })

    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"Save bill error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Unable to save the bill. Please check the entered information and try again.'}), 500

# ----------------- Bills Management & Deletion -----------------

@app.route('/bills')
@login_required
def bills():
    search = request.args.get('search', '').strip()
    period = request.args.get('period', 'all')
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()

    try:
        bills_list = database.get_all_bills(
            search_query=search if search else None,
            filter_period=period,
            from_date=from_date if from_date else None,
            to_date=to_date if to_date else None
        )
        return render_template(
            'bills.html',
            bills=bills_list,
            search=search,
            period=period,
            from_date=from_date,
            to_date=to_date
        )
    except Exception as e:
        logger.error(f"Bills list error: {e}", exc_info=True)
        flash('Unable to load bills.', 'danger')
        return render_template('bills.html', bills=[], search=search, period=period, from_date=from_date, to_date=to_date)

@app.route('/bills/<int:bill_id>')
@login_required
def view_bill(bill_id):
    bill = database.get_bill_by_id(bill_id)
    if not bill:
        flash('Bill not found or has been deleted.', 'danger')
        return redirect(url_for('bills'))

    items = database.get_bill_items(bill_id)
    return render_template('bill_view.html', bill=bill, items=items)

@app.route('/bills/<int:bill_id>/info')
@login_required
def bill_info(bill_id):
    """
    CRITICAL REQUIREMENT (Section 3 & 5):
    Returns bill details and payment status for the Delete Confirmation modal.
    """
    bill = database.get_bill_by_id(bill_id)
    if not bill:
        return jsonify({'success': False, 'message': 'Bill not found.'}), 404

    payments_info = database.has_bill_payments(bill_id)
    return jsonify({
        'success': True,
        'bill': {
            'id': bill['id'],
            'bill_number': bill['bill_number'],
            'customer_name': bill['customer_name'],
            'grand_total': float(bill['grand_total']),
            'has_payments': payments_info['count'] > 0,
            'payment_count': payments_info['count'],
            'payment_amount': payments_info['total_amount']
        }
    })

@app.route('/bills/delete/<int:bill_id>', methods=['POST'])
@login_required
def delete_bill_route(bill_id):
    """
    CRITICAL REQUIREMENT (Section 3, 4, 5, 6, 7):
    Delete an incorrect bill in a database transaction.
    Recalculates customer balance, removes bill items, removes linked payments.
    Never deletes customer or products.
    """
    try:
        deleted_bill = database.delete_bill(bill_id, invoices_folder=app.config['INVOICES_FOLDER'])
        
        # If AJAX request
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f"Bill {deleted_bill['bill_number']} was deleted successfully. Customer account and stats recalculated."
            })
        
        flash(f"Bill {deleted_bill['bill_number']} was deleted successfully. Customer account and store totals have been updated.", 'success')
        return redirect(url_for('bills'))

    except ValueError as ve:
        if request.is_json:
            return jsonify({'success': False, 'message': str(ve)}), 404
        flash(str(ve), 'danger')
        return redirect(url_for('bills'))
    except Exception as e:
        logger.error(f"Delete bill error: {e}", exc_info=True)
        if request.is_json:
            return jsonify({'success': False, 'message': 'Failed to delete bill. Please try again.'}), 500
        flash('Unable to delete bill. Database transaction was rolled back.', 'danger')
        return redirect(url_for('bills'))

@app.route('/bills/<int:bill_id>/pdf')
@login_required
def download_pdf(bill_id):
    bill = database.get_bill_by_id(bill_id)
    if not bill:
        abort(404, description="Bill not found")

    filename = f"{bill['bill_number']}.pdf"
    filepath = os.path.join(app.config['INVOICES_FOLDER'], filename)

    if not os.path.exists(filepath):
        items = database.get_bill_items(bill_id)
        filepath = pdf_generator.generate_pdf_invoice(bill, items, app.config['INVOICES_FOLDER'])
        database.update_bill_pdf_path(bill_id, filepath)

    as_attachment = request.args.get('download', '1') == '1'
    return send_file(
        filepath,
        mimetype='application/pdf',
        as_attachment=as_attachment,
        download_name=filename
    )

# ----------------- Reports -----------------

@app.route('/reports')
@login_required
def reports():
    try:
        report_data = database.get_sales_report_data()
        stats = database.get_dashboard_stats()
        return render_template('reports.html', report_data=report_data, stats=stats)
    except Exception as e:
        logger.error(f"Reports error: {e}", exc_info=True)
        flash('Unable to load reports data.', 'danger')
        return render_template('reports.html', report_data={'monthly_trend': [], 'customer_balances': []}, stats={
            'today_sales': 0.0, 'today_bills': 0, 'monthly_sales': 0.0,
            'total_customers': 0, 'total_outstanding_balance': 0.0
        })

# ----------------- Monthly Statement PDF -----------------

@app.route('/customers/<int:customer_id>/monthly-pdf')
@login_required
def download_monthly_pdf(customer_id):
    """
    Generate and send the monthly account statement PDF.
    Query params: year=YYYY, month=MM
    If no year/month supplied, generates a complete all-time statement.
    """
    cust = database.get_customer_by_id(customer_id)
    if not cust:
        abort(404, description='Customer not found.')

    year  = request.args.get('year',  '').strip()
    month = request.args.get('month', '').strip()

    try:
        shop_settings = database.get_shop_settings()

        if year and month:
            # Specific month statement
            try:
                year_int  = int(year)
                month_int = int(month)
                if not (1 <= month_int <= 12):
                    abort(400, description='Invalid month value.')
            except ValueError:
                abort(400, description='Year and month must be numbers.')

            data = database.get_monthly_bill_data(customer_id, year_int, month_int)
            pdf_path = monthly_pdf.generate_monthly_statement_pdf(
                data, shop_settings,
                output_dir=app.config['INVOICES_FOLDER']
            )
            shop_name = shop_settings.get('shop_name', 'FRUITS_SHOP').upper().replace(' ', '_')
            dl_name = '{}_{}_{}{}.pdf'.format(
                shop_name,
                cust['name'].upper().replace(' ', '_'),
                data['month_name'].upper(),
                year_int
            )
        else:
            # All-time / complete statement
            data = database.get_monthly_bill_data_alltime(customer_id)
            pdf_path = monthly_pdf.generate_monthly_statement_pdf(
                data, shop_settings,
                output_dir=app.config['INVOICES_FOLDER']
            )
            shop_name = shop_settings.get('shop_name', 'FRUITS_SHOP').upper().replace(' ', '_')
            dl_name = '{}_{}_{}.pdf'.format(
                shop_name,
                cust['name'].upper().replace(' ', '_'),
                'COMPLETE_STATEMENT'
            )

        as_attachment = request.args.get('inline', '0') != '1'
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=as_attachment,
            download_name=dl_name
        )

    except ValueError as ve:
        flash(str(ve), 'danger')
        return redirect(url_for('customer_details', customer_id=customer_id))
    except Exception as e:
        logger.error(f'Monthly PDF error: {e}', exc_info=True)
        flash('Unable to generate monthly statement PDF. Please try again.', 'danger')
        return redirect(url_for('customer_details', customer_id=customer_id))

# ----------------- Shop Settings -----------------

@app.route('/settings', methods=['GET'])
@login_required
def settings():
    try:
        shop_settings = database.get_shop_settings()
        return render_template('settings.html', settings=shop_settings)
    except Exception as e:
        logger.error(f'Settings load error: {e}', exc_info=True)
        flash('Unable to load settings.', 'danger')
        return render_template('settings.html', settings={})

@app.route('/settings', methods=['POST'])
@login_required
def save_settings():
    try:
        fields = ['shop_name', 'shop_address', 'shop_phone', 'shop_email', 'shop_gst']
        updates = {f: request.form.get(f, '').strip() for f in fields}
        if not updates.get('shop_name'):
            flash('Shop name cannot be empty.', 'danger')
            return redirect(url_for('settings'))
        database.update_shop_settings(updates)
        flash('Shop settings saved successfully.', 'success')
    except Exception as e:
        logger.error(f'Settings save error: {e}', exc_info=True)
        flash('Unable to save settings. Please try again.', 'danger')
    return redirect(url_for('settings'))

# ----------------- Run Application -----------------

if __name__ == '__main__':
    database.init_db(seed_sample_data=False)
    print("=" * 60)
    print(" DEPARTMENT STORE BILLING SYSTEM")
    print(" Server running on: http://127.0.0.1:5000/")
    print(" Default Login: admin / admin123")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=True)
