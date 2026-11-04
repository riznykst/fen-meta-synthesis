// Scripted screen recording of the /demo flow (Playwright recordVideo).
// Run from web/:  node record_demo.mjs
// Output: ../artifacts/video/demo-<ts>.webm  → converted to .mp4 by assemble step.
import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

const BASE = process.env.FEN_DEMO_BASE || "http://127.0.0.1:8082";
const MOCK = process.env.FEN_MOCK_BASE || "http://127.0.0.1:8103";
const OUT = "../artifacts/video";
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.FEN_CHROME_PATH ||
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"],
});
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: OUT, size: { width: 1280, height: 800 } },
});
const page = await context.newPage();
page.setDefaultTimeout(180000);

async function smoothTo(selector) {
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, selector);
  await sleep(1200);
}

async function glide(delta) {
  await page.evaluate((d) => window.scrollBy({ top: d, behavior: "smooth" }), delta);
  await sleep(1200);
}

console.log("open demo");
await page.goto(`${BASE}/web/portal/demo.html?fen_mock_base=${encodeURIComponent(MOCK)}`);
await page.waitForSelector("#proposals article.item", { timeout: 120000 });
await sleep(4000); // problem statement beat

console.log("show the three-at-a-time window");
await smoothTo("#panel-proposals");
await sleep(6000);

console.log("show all / collapse");
const showAll = page.locator("[data-action='toggle-all']").last();
if (await showAll.count()) {
  await showAll.click();
  await sleep(3500);
  const fewer = page.locator("[data-action='toggle-all']").last();
  if (await fewer.count()) { await fewer.click(); await sleep(1500); }
}

console.log("show in source (inline evidence)");
const firstCard = page.locator("#proposals article.item").first();
await firstCard.scrollIntoViewIfNeeded();
await sleep(800);
await firstCard.locator("[data-action='highlight']").click();
await page.waitForSelector("#sourceView mark", { timeout: 20000 });
await sleep(7000);

console.log("quote check panel");
await smoothTo("#panel-quotes");
await sleep(6000);

console.log("provenance chain");
await smoothTo("#panel-proposals");
const provBtn = page.locator("#proposals article.item [data-action='provenance']").first();
if (await provBtn.count()) {
  await provBtn.click();
  await page.waitForSelector("#provenance", { timeout: 20000 });
  await sleep(7000);
}

console.log("accept as reviewer-1");
const claimId = await firstCard.getAttribute("data-item");
await page.selectOption("#reviewer", "reviewer-1");
await sleep(1500);
const card1 = page.locator(`#proposals article[data-item="${claimId}"]`);
await card1.scrollIntoViewIfNeeded();
await sleep(800);
await card1.locator("[data-verdict='accept']").click();
await page.waitForSelector(`#decided [data-item="${claimId}"]`, { timeout: 30000 });
await sleep(5000);

console.log("switch reviewer-2, same claim again (consensus)");
await smoothTo("#panel-sources");
await page.selectOption("#reviewer", "reviewer-2");
await sleep(2000);
const card2 = page.locator(`#proposals article[data-item="${claimId}"]`);
if ((await card2.count()) > 0) {
  await card2.scrollIntoViewIfNeeded();
  await sleep(1000);
  await card2.locator("[data-verdict='accept']").click();
  await sleep(6000);
}

console.log("decided list + registry");
await smoothTo("#decided");
await sleep(6000);
await glide(420);
await sleep(5000);

console.log("back to top for closing beat");
await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
await sleep(4000);

const videoPath = await page.video().path();
await context.close();
await browser.close();
console.log("VIDEO:", videoPath);
