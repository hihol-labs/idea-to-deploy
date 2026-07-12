export async function GET() {
  const doc = await prisma.documents.findFirst();
  return new Response(JSON.stringify(doc, replacer));
}
export async function search(q: string) {
  return prisma.$queryRaw`SELECT id FROM products WHERE name ILIKE ${"%" + q + "%"}`;
}
export async function submit(order: Order) {
  await repo.createAuditRecord(order.id);
  try { await postDocument(order); } catch (e) { log.error("post failed", e); }
  return formatDateFromIso(order.createdAt);
}
