#!/usr/bin/env node
const path = require("path");
const { spawn } = require("child_process");
const helpers = require("./lib/helpers");

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("--detect")) {
    const servers = await helpers.detectDevServers();
    console.log(JSON.stringify(servers, null, 2));
    return;
  }

  const script = args[0];
  if (!script) {
    console.error("Usage: node run.js --detect | node run.js /tmp/itd-browser-check.js");
    process.exit(2);
  }

  const resolved = path.resolve(script);
  const child = spawn(process.execPath, [resolved], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      NODE_PATH: path.join(__dirname, "node_modules"),
      ITD_PLAYWRIGHT_HARNESS: __dirname,
    },
    stdio: "inherit",
  });

  child.on("exit", (code) => process.exit(code || 0));
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
