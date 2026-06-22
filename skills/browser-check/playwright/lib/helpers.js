const http = require("http");
const https = require("https");

const COMMON_PORTS = [
  3000,
  3001,
  4173,
  5173,
  5174,
  8000,
  8080,
  8787,
  9000,
];

function probe(url, timeoutMs = 700) {
  return new Promise((resolve) => {
    const client = url.startsWith("https:") ? https : http;
    const req = client.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve({
        url,
        status: res.statusCode,
        ok: res.statusCode >= 200 && res.statusCode < 500,
      });
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(null);
    });
    req.on("error", () => resolve(null));
  });
}

async function detectDevServers(ports = COMMON_PORTS) {
  const targets = [];
  for (const port of ports) {
    targets.push(`http://127.0.0.1:${port}`);
    targets.push(`http://localhost:${port}`);
  }

  const results = await Promise.all(targets.map((target) => probe(target)));
  const seen = new Set();
  return results
    .filter((result) => result && result.ok)
    .filter((result) => {
      const key = result.url.replace("127.0.0.1", "localhost");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

async function takeScreenshot(page, name) {
  const safeName = String(name || "browser-check").replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
  const file = `/tmp/${safeName}-${Date.now()}.png`;
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

module.exports = {
  detectDevServers,
  takeScreenshot,
};
