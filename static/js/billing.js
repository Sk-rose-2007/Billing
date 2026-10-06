document.addEventListener('DOMContentLoaded', function () {
  // Elements
  const existingRadio = document.getElementById('type-existing');
  const walkinRadio = document.getElementById('type-walkin');
  const existingBlock = document.getElementById('existing-customer-block');
  const walkinBlock = document.getElementById('walkin-customer-block');
  const customerSelect = document.getElementById('customer-select');
  const walkinNameInput = document.getElementById('walkin-name');
  const walkinPhoneInput = document.getElementById('walkin-phone');

  const billItemsTbody = document.getElementById('bill-items-tbody');
  const addRowBtn = document.getElementById('add-row-btn');
  const quickNewProdBtn = document.getElementById('quick-new-prod-btn');

  const subtotalEl = document.getElementById('subtotal-display');
  const discountInput = document.getElementById('discount-input');
  const grandTotalEl = document.getElementById('grand-total-display');
  const paidAmountInput = document.getElementById('paid-amount-input');
  const balanceEl = document.getElementById('balance-display');
  const payFullBtn = document.getElementById('pay-full-btn');

  const generateBillBtn = document.getElementById('generate-bill-btn');
  const clearBillBtn = document.getElementById('clear-bill-btn');
  const billErrorAlert = document.getElementById('bill-error-alert');

  // Quick Add Product Modal Elements
  const quickProdModal = document.getElementById('quick-add-product-modal');
  const qpNameInput = document.getElementById('qp-name');
  const qpPriceInput = document.getElementById('qp-price');
  const qpUnitInput = document.getElementById('qp-unit');
  const qpErrorEl = document.getElementById('quick-prod-error');
  const qpSubmitBtn = document.getElementById('qp-submit-btn');

  // Clear Bill Modal Elements
  const clearModal = document.getElementById('clear-bill-modal');
  const confirmClearBtn = document.getElementById('confirm-clear-btn');

  // Success Modal Elements
  const successModal = document.getElementById('bill-success-modal');
  const modalBillNum = document.getElementById('modal-bill-number');
  const modalDownloadBtn = document.getElementById('modal-download-btn');
  const modalPrintBtn = document.getElementById('modal-print-btn');
  const modalViewBtn = document.getElementById('modal-view-btn');
  const modalNewBillBtn = document.getElementById('modal-new-bill-btn');
  const modalCloseBtn = document.getElementById('modal-close-btn');

  // Global Products catalog
  let products = window.AVAILABLE_PRODUCTS || [];

  // Toggle Customer Type
  function updateCustomerTypeView() {
    if (existingRadio && existingRadio.checked) {
      if (existingBlock) existingBlock.style.display = 'block';
      if (walkinBlock) walkinBlock.style.display = 'none';
    } else {
      if (existingBlock) existingBlock.style.display = 'none';
      if (walkinBlock) walkinBlock.style.display = 'block';
    }
  }

  if (existingRadio && walkinRadio) {
    existingRadio.addEventListener('change', updateCustomerTypeView);
    walkinRadio.addEventListener('change', updateCustomerTypeView);
    updateCustomerTypeView();
  }

  // Create product options HTML string
  function getProductOptionsHtml(selectedId = '') {
    let options = '<option value="">-- Select Product --</option>';
    products.forEach(p => {
      const isSel = String(p.id) === String(selectedId) ? 'selected' : '';
      options += `<option value="${p.id}" data-price="${p.price}" data-unit="${p.unit}" ${isSel}>${p.name} (₹${parseFloat(p.price).toFixed(2)} / ${p.unit})</option>`;
    });
    return options;
  }

  // Refresh all product dropdowns in the table while preserving current selections
  function refreshAllDropdowns(newSelectedId = null, targetRow = null) {
    const rows = billItemsTbody.querySelectorAll('.bill-item-row');
    rows.forEach(row => {
      const select = row.querySelector('.item-product-select');
      const currentVal = row === targetRow && newSelectedId ? newSelectedId : select.value;
      select.innerHTML = getProductOptionsHtml(currentVal);
      if (row === targetRow && newSelectedId) {
        select.value = newSelectedId;
        select.dispatchEvent(new Event('change'));
      }
    });
  }

  // Add Item Row
  function addRow(productId = '', quantity = 1) {
    const tr = document.createElement('tr');
    tr.className = 'bill-item-row';
    tr.innerHTML = `
      <td>
        <select class="form-control item-product-select" required>
          ${getProductOptionsHtml(productId)}
        </select>
      </td>
      <td style="width: 120px;">
        <input type="number" class="form-control item-qty-input text-right" min="0.01" step="any" value="${quantity}" required>
      </td>
      <td style="width: 140px;">
        <div style="display:flex; align-items:center;">
          <span style="margin-right:4px; font-weight:600;">₹</span>
          <input type="number" class="form-control item-price-input text-right" step="0.01" min="0" value="0.00" readonly style="background:#f8fafc;">
        </div>
      </td>
      <td style="width: 140px;" class="text-right">
        <strong class="item-total-display">₹0.00</strong>
      </td>
      <td style="width: 50px;" class="text-center">
        <button type="button" class="btn btn-sm btn-danger remove-row-btn" title="Remove Item">&times;</button>
      </td>
    `;

    billItemsTbody.appendChild(tr);

    const prodSelect = tr.querySelector('.item-product-select');
    const qtyInput = tr.querySelector('.item-qty-input');
    const priceInput = tr.querySelector('.item-price-input');
    const removeBtn = tr.querySelector('.remove-row-btn');

    prodSelect.addEventListener('change', function () {
      const opt = this.options[this.selectedIndex];
      if (opt && opt.value) {
        const price = parseFloat(opt.getAttribute('data-price')) || 0;
        priceInput.value = price.toFixed(2);
      } else {
        priceInput.value = '0.00';
      }
      calculateTotals();
    });

    qtyInput.addEventListener('input', calculateTotals);

    removeBtn.addEventListener('click', function () {
      tr.remove();
      if (billItemsTbody.children.length === 0) {
        addRow();
      }
      calculateTotals();
    });

    if (productId) {
      prodSelect.dispatchEvent(new Event('change'));
    }

    return tr;
  }

  // Calculate live totals
  function calculateTotals() {
    let subtotal = 0;
    const rows = billItemsTbody.querySelectorAll('.bill-item-row');

    rows.forEach(row => {
      const qty = parseFloat(row.querySelector('.item-qty-input').value) || 0;
      const price = parseFloat(row.querySelector('.item-price-input').value) || 0;
      const rowTotal = Math.max(0, Math.round(qty * price * 100) / 100);
      row.querySelector('.item-total-display').textContent = '₹' + rowTotal.toFixed(2);
      subtotal += rowTotal;
    });

    subtotal = Math.round(subtotal * 100) / 100;
    subtotalEl.textContent = '₹' + subtotal.toFixed(2);

    let discount = parseFloat(discountInput.value) || 0;
    if (discount < 0) discount = 0;
    if (discount > subtotal) {
      discount = subtotal;
      discountInput.value = discount.toFixed(2);
    }

    const grandTotal = Math.max(0, Math.round((subtotal - discount) * 100) / 100);
    grandTotalEl.textContent = '₹' + grandTotal.toFixed(2);

    let paidAmount = parseFloat(paidAmountInput.value);
    if (isNaN(paidAmount) || paidAmount < 0) {
      paidAmount = 0;
    }
    if (paidAmount > grandTotal) {
      paidAmount = grandTotal;
      paidAmountInput.value = paidAmount.toFixed(2);
    }

    const balance = Math.max(0, Math.round((grandTotal - paidAmount) * 100) / 100);
    balanceEl.textContent = '₹' + balance.toFixed(2);
  }

  // Quick Pay Full button
  if (payFullBtn) {
    payFullBtn.addEventListener('click', function () {
      const grandTotal = parseFloat(grandTotalEl.textContent.replace('₹', '')) || 0;
      paidAmountInput.value = grandTotal.toFixed(2);
      calculateTotals();
    });
  }

  if (discountInput) discountInput.addEventListener('input', calculateTotals);
  if (paidAmountInput) paidAmountInput.addEventListener('input', calculateTotals);

  // Add initial row
  if (addRowBtn && billItemsTbody) {
    addRowBtn.addEventListener('click', () => addRow());
    if (billItemsTbody.children.length === 0) {
      addRow();
    }
  }

  // ==================== QUICK ADD PRODUCT DIRECTLY (Section 1 & 2) ====================
  window.openQuickProductModal = function () {
    if (qpErrorEl) {
      qpErrorEl.style.display = 'none';
      qpErrorEl.textContent = '';
    }
    if (qpNameInput) qpNameInput.value = '';
    if (qpPriceInput) qpPriceInput.value = '';
    if (qpUnitInput) qpUnitInput.value = '';
    if (quickProdModal) quickProdModal.classList.add('active');
    if (qpNameInput) qpNameInput.focus();
  };

  window.closeQuickProductModal = function () {
    if (quickProdModal) quickProdModal.classList.remove('active');
  };

  if (quickNewProdBtn) {
    quickNewProdBtn.addEventListener('click', window.openQuickProductModal);
  }

  window.handleQuickProductSubmit = function (e) {
    e.preventDefault();
    if (qpErrorEl) {
      qpErrorEl.style.display = 'none';
      qpErrorEl.textContent = '';
    }

    const name = qpNameInput.value.trim();
    const price = parseFloat(qpPriceInput.value);
    const unit = qpUnitInput.value.trim();

    if (!name) {
      showQpError("Product name is required.");
      return;
    }
    if (isNaN(price) || price <= 0) {
      showQpError("Price must be a valid number greater than 0.");
      return;
    }
    if (!unit) {
      showQpError("Unit is required (e.g. 1kg, 1L, piece).");
      return;
    }

    // Check duplicate locally first
    const duplicate = products.find(p => p.name.toLowerCase() === name.toLowerCase());
    if (duplicate) {
      showQpError("Product already exists. Please use the existing product or edit its price.");
      return;
    }

    if (qpSubmitBtn) {
      qpSubmitBtn.disabled = true;
      qpSubmitBtn.textContent = 'Saving...';
    }

    fetch('/products/quick-add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, price: price, unit: unit })
    })
    .then(res => res.json())
    .then(data => {
      if (qpSubmitBtn) {
        qpSubmitBtn.disabled = false;
        qpSubmitBtn.textContent = 'Add Product';
      }

      if (!data.success) {
        showQpError(data.message || "Failed to add product.");
      } else {
        // Success!
        const newProd = data.product;
        products.push(newProd);

        // Find row to place product in
        const rows = billItemsTbody.querySelectorAll('.bill-item-row');
        let targetRow = null;
        for (let i = 0; i < rows.length; i++) {
          const sel = rows[i].querySelector('.item-product-select');
          if (!sel.value) {
            targetRow = rows[i];
            break;
          }
        }
        if (!targetRow) {
          targetRow = addRow();
        }

        // Close modal
        closeQuickProductModal();

        // Refresh dropdowns and auto-select this new product in targetRow
        refreshAllDropdowns(newProd.id, targetRow);
      }
    })
    .catch(err => {
      if (qpSubmitBtn) {
        qpSubmitBtn.disabled = false;
        qpSubmitBtn.textContent = 'Add Product';
      }
      showQpError("Network error: " + err.message);
    });
  };

  function showQpError(msg) {
    if (qpErrorEl) {
      qpErrorEl.textContent = msg;
      qpErrorEl.style.display = 'block';
    } else {
      alert(msg);
    }
  }

  // ==================== CLEAR BILL MODAL (Section 16) ====================
  window.openClearModal = function () {
    if (clearModal) clearModal.classList.add('active');
  };

  window.closeClearModal = function () {
    if (clearModal) clearModal.classList.remove('active');
  };

  if (clearBillBtn) {
    clearBillBtn.addEventListener('click', window.openClearModal);
  }

  if (confirmClearBtn) {
    confirmClearBtn.addEventListener('click', function () {
      closeClearModal();
      resetBillForm();
    });
  }

  function resetBillForm() {
    hideError();
    billItemsTbody.innerHTML = '';
    addRow();
    discountInput.value = '0.00';
    paidAmountInput.value = '0.00';
    if (walkinNameInput) walkinNameInput.value = '';
    if (walkinPhoneInput) walkinPhoneInput.value = '';
    if (customerSelect) customerSelect.selectedIndex = 0;
    calculateTotals();
  }

  // Error alert helpers
  function showError(msg) {
    if (billErrorAlert) {
      billErrorAlert.textContent = msg;
      billErrorAlert.style.display = 'block';
      billErrorAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      alert(msg);
    }
  }

  function hideError() {
    if (billErrorAlert) {
      billErrorAlert.style.display = 'none';
      billErrorAlert.textContent = '';
    }
  }

  // ==================== GENERATE BILL SUBMISSION (Section 9) ====================
  if (generateBillBtn) {
    generateBillBtn.addEventListener('click', function () {
      hideError();

      const customerType = existingRadio && existingRadio.checked ? 'existing' : 'walkin';
      let customerId = null;
      let customerName = '';
      let customerPhone = '';

      if (customerType === 'existing') {
        if (!customerSelect || !customerSelect.value) {
          showError('Please select an existing account customer.');
          return;
        }
        customerId = parseInt(customerSelect.value);
        customerName = customerSelect.options[customerSelect.selectedIndex].text.split(' - Due:')[0].trim();
      } else {
        customerName = walkinNameInput ? walkinNameInput.value.trim() : '';
        customerPhone = walkinPhoneInput ? walkinPhoneInput.value.trim() : '';
        if (!customerName) {
          showError('Customer name is required for walk-in customer.');
          return;
        }
      }

      const rows = billItemsTbody.querySelectorAll('.bill-item-row');
      if (rows.length === 0) {
        showError('Please add at least one product to the bill.');
        return;
      }

      const items = [];
      let hasInvalidItem = false;

      rows.forEach(row => {
        const prodSelect = row.querySelector('.item-product-select');
        const qtyInput = row.querySelector('.item-qty-input');
        const priceInput = row.querySelector('.item-price-input');

        const prodId = prodSelect.value;
        const qty = parseFloat(qtyInput.value);
        const price = parseFloat(priceInput.value);
        const prodName = prodSelect.options[prodSelect.selectedIndex]?.text?.split(' (₹')[0] || '';

        if (!prodId) {
          hasInvalidItem = true;
          return;
        }
        if (isNaN(qty) || qty <= 0) {
          hasInvalidItem = true;
          return;
        }
        if (isNaN(price) || price < 0) {
          hasInvalidItem = true;
          return;
        }

        items.push({
          product_id: parseInt(prodId),
          product_name: prodName,
          quantity: qty,
          price: price
        });
      });

      if (hasInvalidItem || items.length === 0) {
        showError('Please make sure every row has a product selected and a quantity greater than zero.');
        return;
      }

      const discount = parseFloat(discountInput.value) || 0;
      const paidAmount = parseFloat(paidAmountInput.value) || 0;
      const grandTotal = parseFloat(grandTotalEl.textContent.replace('₹', '')) || 0;

      if (discount < 0) {
        showError('Discount cannot be negative.');
        return;
      }
      if (paidAmount < 0) {
        showError('Paid amount cannot be negative.');
        return;
      }
      if (paidAmount > (grandTotal + 0.001)) {
        showError(`Paid amount (₹${paidAmount.toFixed(2)}) cannot exceed Grand Total (₹${grandTotal.toFixed(2)}).`);
        return;
      }

      generateBillBtn.disabled = true;
      generateBillBtn.textContent = 'Generating PDF Bill...';

      const payload = {
        customer_type: customerType,
        customer_id: customerId,
        customer_name: customerName,
        customer_phone: customerPhone,
        items: items,
        discount: discount,
        paid_amount: paidAmount
      };

      fetch('/billing/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json().then(data => ({ status: res.status, body: data })))
      .then(result => {
        generateBillBtn.disabled = false;
        generateBillBtn.innerHTML = '&#128462; GENERATE PDF BILL';

        if (result.status >= 400 || !result.body.success) {
          showError(result.body.message || 'An error occurred while saving the bill.');
        } else {
          const data = result.body;
          if (modalBillNum) modalBillNum.textContent = data.bill_number;
          if (modalDownloadBtn) modalDownloadBtn.href = data.download_url;
          if (modalViewBtn) modalViewBtn.href = data.view_url;
          if (modalPrintBtn) {
            modalPrintBtn.onclick = function () {
              const printWin = window.open(data.view_url, '_blank');
              if (printWin) {
                printWin.onload = function () {
                  printWin.print();
                };
              }
            };
          }

          if (successModal) {
            successModal.classList.add('active');
          }
        }
      })
      .catch(err => {
        generateBillBtn.disabled = false;
        generateBillBtn.innerHTML = '&#128462; GENERATE PDF BILL';
        showError('Network error or server unavailable: ' + err.message);
      });
    });
  }

  // Modal event listeners
  if (modalCloseBtn && successModal) {
    modalCloseBtn.addEventListener('click', function () {
      successModal.classList.remove('active');
    });
  }

  if (modalNewBillBtn && successModal) {
    modalNewBillBtn.addEventListener('click', function () {
      successModal.classList.remove('active');
      resetBillForm();
    });
  }

  // Escape key closes modals
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      window.closeQuickProductModal();
      window.closeClearModal();
      if (successModal) successModal.classList.remove('active');
    }
  });
});
