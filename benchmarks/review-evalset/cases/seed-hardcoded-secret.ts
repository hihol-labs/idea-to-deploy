const OZON_API_KEY = "a91f4c2e88b34d17bc55f0d9e2ab3c41";
export function client() { return fetch(url, { headers: { "Api-Key": OZON_API_KEY } }); }
