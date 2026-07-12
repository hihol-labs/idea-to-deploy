export async function search(q: string) {
  return prisma.$queryRawUnsafe(`SELECT * FROM products WHERE name ILIKE '%${q}%'`);
}
