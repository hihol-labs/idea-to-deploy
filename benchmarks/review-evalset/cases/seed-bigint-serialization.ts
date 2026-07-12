export async function GET() {
  const doc = await prisma.documents.findFirst({ include: { header: true } });
  return NextResponse.json(doc);
}
