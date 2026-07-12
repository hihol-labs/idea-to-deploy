ALTER TABLE purchase_invoice_goods
  ADD COLUMN batch_order_id INTEGER REFERENCES documents(id);
