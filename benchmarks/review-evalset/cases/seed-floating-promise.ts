export function submit(order: Order) {
  repo.createAuditRecord(order.id);
  return { ok: true };
}
