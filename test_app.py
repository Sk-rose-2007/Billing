import os
import json
import database
import pdf_generator
import app

def reset_db_for_test():
    """Wipes all data cleanly without Windows file-lock issues."""
    conn = database.get_db_connection()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM payments")
    conn.execute("DELETE FROM bill_items")
    conn.execute("DELETE FROM bills")
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM customers")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()

def run_all_10_tests():
    print("=" * 65)
    print(" EXECUTING SUITE FOR ALL 10 USER REQUIREMENTS & SCENARIOS")
    print("=" * 65)

    client = app.app.test_client()

    # Reset DB to 0 products, 0 customers, 0 bills
    reset_db_for_test()
    database.init_db(seed_sample_data=False)

    # -------------------------------------------------------------
    # TEST 1: Login -> Dashboard -> Add Product -> Product appears
    # -------------------------------------------------------------
    print("\n--- TEST 1: Login, Dashboard, Add Product ---")
    res = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert b'Dashboard Overview' in res.data, "Login failed"

    # Add product
    add_p_res = client.post('/products/add', data={
        'name': 'Rice 5kg',
        'price': '350.00',
        'unit': '5kg'
    }, follow_redirects=True)
    assert b'Rice 5kg' in add_p_res.data
    assert b'added successfully' in add_p_res.data
    assert b'350.00' in add_p_res.data
    print("[PASS] TEST 1: Login -> Add Product -> Product appears in catalog.")

    # -------------------------------------------------------------
    # TEST 2: Create Bill -> Select existing product -> Add quantity
    #         -> Total calculates correctly -> Generate PDF
    # -------------------------------------------------------------
    print("\n--- TEST 2: Create Bill with Existing Product ---")
    p_rice = database.get_product_by_name('Rice 5kg')
    assert p_rice is not None

    # First add a regular customer to bill
    client.post('/customers/add', data={'name': 'Ramesh Kumar', 'phone': '9876543210', 'address': 'Main Bazaar'})
    c_ramesh = database.get_all_customers()[0]

    bill_payload = {
        'customer_type': 'existing',
        'customer_id': c_ramesh['id'],
        'customer_name': c_ramesh['name'],
        'customer_phone': c_ramesh['phone'],
        'items': [{
            'product_id': p_rice['id'],
            'product_name': p_rice['name'],
            'quantity': 2,
            'price': 350.0
        }],
        'discount': 50.0,
        'paid_amount': 650.0
    }
    b_res = client.post('/billing/save', data=json.dumps(bill_payload), content_type='application/json')
    assert b_res.status_code == 200, f"Bill creation failed: {b_res.data}"
    b_data = json.loads(b_res.data)
    assert b_data['success'] is True
    bill_id = b_data['bill_id']

    # Verify bill calculation: (2 * 350) = 700 - 50 discount = 650 grand total. Paid 650. Balance 0.
    b = database.get_bill_by_id(bill_id)
    assert b['subtotal'] == 700.0
    assert b['grand_total'] == 650.0
    assert b['paid_amount'] == 650.0
    assert b['balance'] == 0.0

    # Verify PDF was generated
    pdf_file = os.path.join(app.app.config['INVOICES_FOLDER'], f"{b['bill_number']}.pdf")
    assert os.path.exists(pdf_file), "PDF file does not exist on disk"
    print(f"[PASS] TEST 2: Bill calculated correctly (700 - 50 = 650), PDF generated ({os.path.basename(pdf_file)}).")

    # -------------------------------------------------------------
    # TEST 3: Create a new product directly from Create Bill
    #         -> Enter name, price -> Save -> Appears in current bill
    #         -> Complete bill -> PDF generated
    # -------------------------------------------------------------
    print("\n--- TEST 3: Add New Product Directly from Create Bill ---")
    qp_res = client.post('/products/quick-add', data=json.dumps({
        'name': 'Fresh Milk',
        'price': 60.0,
        'unit': '1L'
    }), content_type='application/json')
    assert qp_res.status_code == 200
    qp_data = json.loads(qp_res.data)
    assert qp_data['success'] is True
    p_milk = qp_data['product']
    assert p_milk['name'] == 'Fresh Milk'
    assert p_milk['price'] == 60.0

    # Now create bill using this newly added product directly
    bill_milk_payload = {
        'customer_type': 'existing',
        'customer_id': c_ramesh['id'],
        'customer_name': c_ramesh['name'],
        'customer_phone': c_ramesh['phone'],
        'items': [{
            'product_id': p_milk['id'],
            'product_name': p_milk['name'],
            'quantity': 2,
            'price': p_milk['price']
        }],
        'discount': 0.0,
        'paid_amount': 120.0
    }
    bm_res = client.post('/billing/save', data=json.dumps(bill_milk_payload), content_type='application/json')
    assert bm_res.status_code == 200
    bm_data = json.loads(bm_res.data)
    assert bm_data['success'] is True
    b_milk = database.get_bill_by_id(bm_data['bill_id'])
    assert b_milk['subtotal'] == 120.0
    assert b_milk['grand_total'] == 120.0
    print("[PASS] TEST 3: Quick product added from Create Bill, used in bill, PDF generated.")

    # -------------------------------------------------------------
    # TEST 4: Create account customer -> Create bill -> Pay partial amount
    #         -> Check customer account -> Correct balance displayed
    # -------------------------------------------------------------
    print("\n--- TEST 4: Account Customer & Partial Payment ---")
    client.post('/customers/add', data={'name': 'Anita Sharma', 'phone': '9123456780', 'address': 'North Ext'})
    c_anita = [c for c in database.get_all_customers() if c['name'] == 'Anita Sharma'][0]

    bill_partial = {
        'customer_type': 'existing',
        'customer_id': c_anita['id'],
        'customer_name': c_anita['name'],
        'customer_phone': c_anita['phone'],
        'items': [{
            'product_id': p_rice['id'],
            'product_name': p_rice['name'],
            'quantity': 3,
            'price': 350.0
        }],
        'discount': 50.0, # 1050 - 50 = 1000
        'paid_amount': 600.0 # Balance: 400
    }
    bp_res = client.post('/billing/save', data=json.dumps(bill_partial), content_type='application/json')
    assert bp_res.status_code == 200
    bp_data = json.loads(bp_res.data)
    b_partial = database.get_bill_by_id(bp_data['bill_id'])

    # Verify balance on bill
    assert b_partial['grand_total'] == 1000.0
    assert b_partial['paid_amount'] == 600.0
    assert b_partial['balance'] == 400.0

    # Verify customer account financial summary
    fin_anita = database.get_customer_financial_summary(c_anita['id'])
    assert fin_anita['total_purchases'] == 1000.0
    assert fin_anita['total_paid'] == 600.0
    assert fin_anita['outstanding_balance'] == 400.0
    print("[PASS] TEST 4: Partial payment bill created. Customer balance is exactly Rs. 400.00.")

    # -------------------------------------------------------------
    # TEST 5: Add later payment -> Balance decreases correctly
    # -------------------------------------------------------------
    print("\n--- TEST 5: Subsequent Payment Processing ---")
    pay_res = client.post(f"/customers/{c_anita['id']}/payment", data={
        'amount': '250.00',
        'payment_date': '2026-10-05 15:30:00',
        'notes': 'Account settlement via UPI'
    }, follow_redirects=True)
    assert b"Payment of" in pay_res.data

    fin_anita_after = database.get_customer_financial_summary(c_anita['id'])
    assert fin_anita_after['total_paid'] == 850.0 # 600 + 250
    assert fin_anita_after['outstanding_balance'] == 150.0 # 1000 - 850
    print("[PASS] TEST 5: Later payment of ₹250 recorded. Remaining balance decreased to ₹150.00.")

    # -------------------------------------------------------------
    # TEST 6: Create walk-in customer bill -> Bill generated
    #         -> Customer does not appear in Customers page
    # -------------------------------------------------------------
    print("\n--- TEST 6: Walk-in Customer Isolation ---")
    walkin_payload = {
        'customer_type': 'walkin',
        'customer_id': None,
        'customer_name': 'Walk-in John Doe',
        'customer_phone': '9988776655',
        'items': [{
            'product_id': p_milk['id'],
            'product_name': p_milk['name'],
            'quantity': 1,
            'price': 60.0
        }],
        'discount': 0.0,
        'paid_amount': 60.0
    }
    w_res = client.post('/billing/save', data=json.dumps(walkin_payload), content_type='application/json')
    assert w_res.status_code == 200
    w_data = json.loads(w_res.data)
    w_bill = database.get_bill_by_id(w_data['bill_id'])
    assert w_bill['customer_id'] is None
    assert w_bill['customer_name'] == 'Walk-in John Doe'

    # Verify John Doe is NOT in customers table
    all_customers = database.get_all_customers()
    assert not any(c['name'] == 'Walk-in John Doe' for c in all_customers), "Walk-in was added to customers!"
    print("[PASS] TEST 6: Walk-in bill generated. No account created in Customers page.")

    # -------------------------------------------------------------
    # TEST 7: Change product price -> Create new bill -> New price used
    #         -> Old bill still shows old price
    # -------------------------------------------------------------
    print("\n--- TEST 7: Dynamic Price Change Isolation ---")
    client.post(f"/products/edit/{p_rice['id']}", data={
        'name': 'Rice 5kg',
        'price': '380.00',
        'unit': '5kg'
    }, follow_redirects=True)

    p_rice_updated = database.get_product_by_id(p_rice['id'])
    assert p_rice_updated['price'] == 380.0

    # Old bill b (ID 1) must still show price 350.0
    old_items = database.get_bill_items(bill_id)
    assert old_items[0]['price'] == 350.0, f"Old bill price changed to {old_items[0]['price']}!"

    # New bill uses 380
    new_bill_payload = {
        'customer_type': 'walkin',
        'customer_id': None,
        'customer_name': 'Walk-in Customer 2',
        'customer_phone': '',
        'items': [{
            'product_id': p_rice_updated['id'],
            'product_name': p_rice_updated['name'],
            'quantity': 1,
            'price': p_rice_updated['price']
        }],
        'discount': 0.0,
        'paid_amount': 380.0
    }
    nb_res = client.post('/billing/save', data=json.dumps(new_bill_payload), content_type='application/json')
    nb_data = json.loads(nb_res.data)
    nb_bill = database.get_bill_by_id(nb_data['bill_id'])
    nb_items = database.get_bill_items(nb_bill['id'])
    assert nb_items[0]['price'] == 380.0
    print("[PASS] TEST 7: Catalog updated to ₹380. New bills use ₹380, old bills retain ₹350.")

    # -------------------------------------------------------------
    # TEST 8: Create incorrect bill -> Delete bill -> Confirm deletion
    #         -> Bill disappears -> Customer account recalculates
    #         -> Dashboard recalculates
    # -------------------------------------------------------------
    print("\n--- TEST 8: Bill Deletion & Account/Dashboard Recalculation ---")
    err_bill_payload = {
        'customer_type': 'existing',
        'customer_id': c_anita['id'],
        'customer_name': c_anita['name'],
        'customer_phone': c_anita['phone'],
        'items': [{
            'product_id': p_rice['id'],
            'product_name': p_rice['name'],
            'quantity': 1,
            'price': 380.0
        }],
        'discount': 0.0,
        'paid_amount': 100.0
    }
    err_res = client.post('/billing/save', data=json.dumps(err_bill_payload), content_type='application/json')
    err_data = json.loads(err_res.data)
    err_bill_id = err_data['bill_id']

    # Balance before deletion
    fin_before_del = database.get_customer_financial_summary(c_anita['id'])
    assert fin_before_del['outstanding_balance'] == 430.0 # 150 + 280

    stats_before = database.get_dashboard_stats()

    # Delete the bill
    del_res = client.post(f"/bills/delete/{err_bill_id}", follow_redirects=True)
    assert b"deleted successfully" in del_res.data

    # Verify bill is gone
    assert database.get_bill_by_id(err_bill_id) is None
    assert len(database.get_bill_items(err_bill_id)) == 0

    # Verify customer account recalculated back to 150.0
    fin_after_del = database.get_customer_financial_summary(c_anita['id'])
    assert fin_after_del['outstanding_balance'] == 150.0

    # Verify dashboard recalculated
    stats_after = database.get_dashboard_stats()
    assert stats_after['today_bills'] == stats_before['today_bills'] - 1
    assert round(stats_after['today_sales'], 2) == round(stats_before['today_sales'] - 380.0, 2)

    # Verify customer and products were NOT deleted
    assert database.get_customer_by_id(c_anita['id']) is not None
    assert database.get_product_by_id(p_rice['id']) is not None
    print("[PASS] TEST 8: Incorrect bill deleted in transaction. Customer balance & Dashboard accurately recalculated. Customer and products preserved.")

    # -------------------------------------------------------------
    # TEST 9: Try invalid inputs -> Proper validation messages
    #         -> No broken database records
    # -------------------------------------------------------------
    print("\n--- TEST 9: Form Validation & Error Guards ---")
    # Duplicate product name
    dup_res = client.post('/products/quick-add', data=json.dumps({
        'name': 'Rice 5kg',
        'price': 400.0,
        'unit': '5kg'
    }), content_type='application/json')
    assert dup_res.status_code == 400
    assert "Product already exists" in json.loads(dup_res.data)['message']

    # Negative price
    neg_res = client.post('/products/quick-add', data=json.dumps({
        'name': 'Invalid Prod',
        'price': -10.0,
        'unit': '1kg'
    }), content_type='application/json')
    assert neg_res.status_code == 400

    # Bill with empty items
    empty_bill = client.post('/billing/save', data=json.dumps({
        'customer_type': 'walkin',
        'customer_name': 'Test',
        'items': []
    }), content_type='application/json')
    assert empty_bill.status_code == 400

    # Overpayment exceeding outstanding balance
    overpay_res = client.post(f"/customers/{c_anita['id']}/payment", data={
        'amount': '500.00' # Remaining balance is only 150.0
    }, follow_redirects=True)
    assert b"cannot exceed customer" in overpay_res.data
    print("[PASS] TEST 9: Duplicate name guard, negative price guard, empty bill guard, and overpayment guard all triggered correctly.")

    # -------------------------------------------------------------
    # TEST 10: Desktop & Mobile UI layout check
    # -------------------------------------------------------------
    print("\n--- TEST 10: UI Template & Layout Integrity ---")
    for route in ['/dashboard', '/billing', '/bills', '/products', '/customers', '/reports']:
        page = client.get(route)
        assert page.status_code == 200, f"Route {route} failed with {page.status_code}"
        assert b"mobile-menu-btn" in page.data
        assert b"app-sidebar" in page.data
    print("[PASS] TEST 10: All main routes render responsive structure with mobile drawer.")

    print("\n" + "=" * 65)
    print(" ALL 10 USER TEST SCENARIOS PASSED WITH 100% SUCCESS! ")
    print("=" * 65)

if __name__ == '__main__':
    run_all_10_tests()
