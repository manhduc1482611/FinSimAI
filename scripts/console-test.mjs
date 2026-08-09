/**
 * console-test.mjs — tự mở các trang của app bằng Chrome headless (CDP),
 * thu thập lỗi console / exception / network 4xx-5xx / cảnh báo preload,
 * rồi in báo cáo. Không cần dependency — dùng fetch + WebSocket của Node.
 *
 * Cách chạy:
 *   node scripts/console-test.mjs                      # bản sạch (chưa đăng nhập)
 *   node scripts/console-test.mjs --token=XYZ          # với token giả để test luồng 401
 *   node scripts/console-test.mjs --routes=/social     # chỉ chạy vài route
 *
 * Exit code: 0 nếu không có lỗi, 1 nếu có.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SETTLE_MS = Number(process.env.SETTLE_MS ?? 5000);
const CHROME =
  process.env.CHROME_PATH ??
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";

let PORT = 0;

/** Chọn port CDP rảnh để tránh xung đột với instance trước còn sót. */
async function pickFreePort() {
  const explicit = Number(process.env.CDP_PORT ?? 0);
  if (explicit > 0) {
    return explicit;
  }
  const net = await import("node:net");
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function buildChromeFlags() {
  return [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-gpu",
    "--disable-extensions",
    "--window-size=1440,900",
  ];
}

const DEFAULT_ROUTES = ["/", "/login", "/dashboard", "/social", "/trade", "/news", "/companies", "/contests", "/tasks", "/trade/mentor"];

const args = process.argv.slice(2);
const staleTokenArg = args.find((a) => a.startsWith("--token="));
const STALE_TOKEN = staleTokenArg ? staleTokenArg.slice("--token=".length) : null;
const routesArg = args.find((a) => a.startsWith("--routes="));
const ROUTES = routesArg
  ? routesArg.slice("--routes=".length).split(",").map((r) => (r.startsWith("/") ? r : `/${r}`))
  : DEFAULT_ROUTES;

const report = [];

function cdpClient(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  let nextId = 1;
  const listeners = new Map();

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id !== undefined) {
      const p = pending.get(msg.id);
      if (p) {
        pending.delete(msg.id);
        if (msg.error) p.reject(new Error(msg.error.message));
        else p.resolve(msg.result);
      }
    } else if (msg.method) {
      const list = listeners.get(msg.method) ?? [];
      for (const cb of list) cb(msg.params);
    }
  };

  return new Promise((resolve, reject) => {
    ws.onopen = () => {
      resolve({
        send(method, params = {}) {
          const id = nextId++;
          ws.send(JSON.stringify({ id, method, params }));
          return new Promise((res, rej) => pending.set(id, { resolve: res, reject: rej }));
        },
        on(method, cb) {
          listeners.set(method, [...(listeners.get(method) ?? []), cb]);
        },
        close() {
          ws.close();
        },
      });
    };
    ws.onerror = (e) => reject(new Error(`WS error: ${e.message ?? "unknown"}`));
  });
}

async function getVersion() {
  const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
  return res.json();
}

async function newTarget(url) {
  let res = await fetch(
    `http://127.0.0.1:${PORT}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  );
  if (res.status >= 400) {
    res = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent("about:blank")}`);
  }
  return res.json();
}

async function closeTarget(targetId) {
  try {
    await fetch(`http://127.0.0.1:${PORT}/json/close/${targetId}`);
  } catch {
    /* bỏ qua */
  }
}

function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function probePage(url, label, token) {
  const issues = [];
  const requestUrls = new Map();
  const target = await newTarget("about:blank");
  const client = await cdpClient(target.webSocketDebuggerUrl);
  try {
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Network.enable");
    await client.send("Log.enable");

    client.on("Network.requestWillBeSent", (p) => {
      requestUrls.set(p.requestId, p.request.url);
    });

    if (token) {
      await client.send("Page.addScriptToEvaluateOnNewDocument", {
        source: `try { localStorage.setItem("finsim.access_token", ${JSON.stringify(token)}); } catch (e) {}`,
      });
    }

    client.on("Runtime.consoleAPICalled", (p) => {
      if (p.type === "error" || p.type === "warning") {
        const text = (p.args ?? []).map((a) => a.value ?? a.description ?? a.type ?? "").join(" ");
        issues.push({ kind: "console", level: p.type, text });
      }
    });
    client.on("Runtime.exceptionThrown", (p) => {
      const d = p.exceptionDetails;
      issues.push({
        kind: "exception",
        level: "error",
        text: (d.exception?.description ?? d.text ?? "exception").slice(0, 500),
      });
    });
    client.on("Log.entryAdded", (p) => {
      const e = p.entry;
      if (e.level === "error" || e.level === "warning") {
        issues.push({ kind: "log", level: e.level, text: e.text });
      }
    });
    client.on("Network.loadingFailed", (p) => {
      // ERR_ABORTED thường là prefetch/navigation bị hủy khi chuyển trang — bỏ qua.
      if (p.errorText === "net::ERR_ABORTED") {
        return;
      }
      const url = requestUrls.get(p.requestId) ?? "";
      issues.push({
        kind: "network",
        level: "error",
        text: `LOAD FAILED ${p.type ?? ""} ${p.errorText ?? ""} ${url}`,
      });
    });
    client.on("Network.responseReceived", (p) => {
      if (p.response.status >= 400) {
        issues.push({
          kind: "http",
          level: "error",
          text: `HTTP ${p.response.status} ${p.response.url}`,
        });
      }
    });

    await client.send("Page.navigate", { url: `${BASE}${url}` });
    await wait(SETTLE_MS);
    issues.forEach((i) => report.push({ label, ...i }));
  } finally {
    client.close();
    await closeTarget(target.id);
  }
}

async function main() {
  PORT = await pickFreePort();
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "finsim-console-"));
  const chrome = spawn(
    CHROME,
    [...buildChromeFlags(), `--user-data-dir=${userDataDir}`, "about:blank"],
    { stdio: "ignore" },
  );

  let debugUrl = null;
  for (let i = 0; i < 40 && !debugUrl; i++) {
    try {
      const v = await getVersion();
      debugUrl = v.webSocketDebuggerUrl;
    } catch {
      await wait(250);
    }
  }
  if (!debugUrl) {
    console.error("Không kết nối được Chrome CDP — kiểm tra CHROME_PATH / CDP_PORT.");
    chrome.kill();
    process.exit(2);
  }

  console.log(
    `Chrome CDP OK · base=${BASE} · ${ROUTES.length} routes · ${STALE_TOKEN ? "scenario=stale-token" : "scenario=clean"}\n`,
  );

  for (const route of ROUTES) {
    await probePage(route, route, STALE_TOKEN);
  }

  try {
    spawn("taskkill", ["/pid", String(chrome.pid), "/T", "/F"], { stdio: "ignore" });
  } catch {
    /* bỏ qua */
  }

  if (report.length === 0) {
    console.log(`\u2713 Không có lỗi console trên ${ROUTES.length} route.`);
    process.exit(0);
  }

  console.log(`\u00d7 ${report.length} vấn đề:\n`);
  const byLabel = new Map();
  for (const r of report) {
    const list = byLabel.get(r.label) ?? [];
    list.push(r);
    byLabel.set(r.label, list);
  }
  for (const [label, list] of byLabel) {
    console.log(`--- ${label} ---`);
    for (const i of list) {
      const prefix = `[${i.kind}/${i.level}]`;
      console.log(`  ${prefix} ${i.text}`);
    }
    console.log("");
  }
  process.exit(1);
}

main().catch((e) => {
  console.error("Lỗi harness:", e);
  process.exit(2);
});
