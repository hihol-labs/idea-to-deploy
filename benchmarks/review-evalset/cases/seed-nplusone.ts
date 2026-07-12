export async function loadOrders(ids: number[]) {
  const out = [] as any[];
  for (const id of ids) {
    const row = await prisma.customerOrderHeader.findUnique({ where: { id } });
    out.push(row);
  }
  return out;
}
