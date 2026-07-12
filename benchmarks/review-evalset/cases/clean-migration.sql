ALTER TABLE purchase_invoice_goods
  ADD COLUMN warehouse_id INTEGER REFERENCES structural_units(id);
CREATE INDEX idx_pig_warehouse_id ON purchase_invoice_goods(warehouse_id);
