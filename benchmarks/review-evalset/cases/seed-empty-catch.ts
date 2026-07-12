export async function post(doc: Doc) {
  try {
    await postDocument(doc);
  } catch (e) {}
}
