// Scripted screen recording of the /demo flow (Playwright recordVideo).
// Run from web/:  node record_demo.mjs
// Output: ../artifacts/video/page@*.webm → mp4 in the assemble step.
//
// Headless Chrome paints no mouse pointer, so a synthetic one is injected into
// the page: an arrow that glides to each target plus a click ripple. The real
// mouse is moved too, so :hover states still fire. Cursor moves live inside the
// existing pauses, keeping the clip length (and the narration cues) unchanged.
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

const CURSOR_CSS = `
#fen-cursor{position:fixed;left:0;top:0;width:30px;height:36px;z-index:2147483647;
  pointer-events:none;transform:translate(620px,400px);
  transition:transform 420ms cubic-bezier(.22,.75,.2,1), filter 120ms ease;}
#fen-cursor svg{filter:drop-shadow(0 2px 4px rgba(0,0,0,.55));}
#fen-cursor.press{filter:brightness(.85);}
#fen-ripple{position:fixed;left:0;top:0;width:52px;height:52px;margin:-26px 0 0 -26px;
  border-radius:50%;border:2px solid rgba(45,90,142,.9);
  background:rgba(45,90,142,.22);z-index:2147483646;pointer-events:none;opacity:0;}
#fen-ripple.go{animation:fenRipple .5s ease-out;}
@keyframes fenRipple{0%{opacity:.95;transform:scale(.3)}100%{opacity:0;transform:scale(1.25)}}
`;

async function installCursor() {
  await page.addStyleTag({ content: CURSOR_CSS });
  await page.evaluate(() => {
    const arrow = document.createElement("div");
    arrow.id = "fen-cursor";
    arrow.innerHTML =
      '<svg width="30" height="36" viewBox="0 0 22 26" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M2 2 L2 20 L7 15.5 L10.5 23.5 L14 22 L10.5 14.5 L17 14.5 Z" ' +
      'fill="#ffffff" stroke="#0f172a" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(arrow);
    const ripple = document.createElement("div");
    ripple.id = "fen-ripple";
    document.body.appendChild(ripple);
    window.__fenCursorMove = (x, y) => {
      const maxX = window.innerWidth - 34;
      const maxY = window.innerHeight - 40;
      const cx = Math.max(6, Math.min(x, maxX));
      const cy = Math.max(6, Math.min(y, maxY));
      arrow.style.transform = `translate(${cx - 2}px, ${cy - 2}px)`;
    };
    window.__fenCursorPress = () => {
      arrow.classList.add("press");
      setTimeout(() => arrow.classList.remove("press"), 130);
    };
    window.__fenRipple = (x, y) => {
      ripple.style.left = x + "px";
      ripple.style.top = y + "px";
      ripple.classList.remove("go");
      void ripple.offsetWidth;
      ripple.classList.add("go");
    };
  });
}

async function aim(selector, settleMs = 420) {
  const locator = page.locator(selector).first();
  return aimLocator(locator, settleMs);
}

async function aimLocator(locator, settleMs = 420) {
  // Bring the target into view first: a fixed-position pointer aimed at an
  // off-screen box would be clamped to the edge and look wrong.
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  const box = await locator.boundingBox();
  if (!box) return null;
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + box.height / 2);
  await page.evaluate(([px, py]) => window.__fenCursorMove(px, py), [x, y]);
  await page.mouse.move(x, y); // real hover states
  await sleep(settleMs);
  return { x, y };
}

async function clickWithCursor(selector, settleMs = 420) {
  return clickLocatorWithCursor(page.locator(selector), settleMs);
}

async function clickLocatorWithCursor(locator, settleMs = 420) {
  const target = locator.first();
  const point = await aimLocator(target, settleMs);
  if (!point) return false;
  await page.evaluate(([px, py]) => window.__fenRipple(px, py), [point.x, point.y]);
  await page.evaluate(() => window.__fenCursorPress());
  await sleep(90);
  await target.click();
  await sleep(230);
  return true;
}

async function chooseWithCursor(value) {
  const box = await page.locator("#reviewer").boundingBox();
  if (box) {
    const x = Math.round(box.x + box.width / 2);
    const y = Math.round(box.y + box.height / 2);
    await page.evaluate(([px, py]) => window.__fenCursorMove(px, py), [x, y]);
    await page.mouse.move(x, y);
    await sleep(300);
    await page.evaluate(([px, py]) => window.__fenRipple(px, py), [x, y]);
    await sleep(90);
  }
  await page.selectOption("#reviewer", value);
  await sleep(230);
}

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
await installCursor();
await sleep(4000); // problem statement beat

console.log("show the three-at-a-time window");
await smoothTo("#panel-proposals");
await sleep(6000);

console.log("show all / collapse (with cursor)");
const showAll = page.locator("[data-action='toggle-all']");
if (await showAll.count()) {
  await clickLocatorWithCursor(showAll.last());
  await sleep(2600);
  const fewer = page.locator("[data-action='toggle-all']");
  if (await fewer.count()) { await clickLocatorWithCursor(fewer.last()); await sleep(600); }
}

console.log("show in source (inline evidence)");
const firstCard = page.locator("#proposals article.item").first();
await firstCard.scrollIntoViewIfNeeded();
await sleep(500);
await clickWithCursor("#proposals article.item [data-action='highlight']");
await page.waitForSelector("#sourceView mark", { timeout: 20000 });
await sleep(6100);

console.log("quote check panel");
await smoothTo("#panel-quotes");
await sleep(6000);

console.log("provenance chain");
await smoothTo("#panel-proposals");
const provBtn = page.locator("#proposals article.item [data-action='provenance']").first();
if (await provBtn.count()) {
  await clickWithCursor("#proposals article.item [data-action='provenance']");
  await page.waitForSelector("#provenance", { timeout: 20000 });
  await sleep(6100);
}

console.log("accept as reviewer-1");
const claimId = await firstCard.getAttribute("data-item");
await chooseWithCursor("reviewer-1");
await sleep(900);
const card1 = page.locator(`#proposals article[data-item="${claimId}"]`);
await card1.scrollIntoViewIfNeeded();
await sleep(400);
await clickWithCursor(`#proposals article[data-item="${claimId}"] [data-verdict='accept']`);
await page.waitForSelector(`#decided [data-item="${claimId}"]`, { timeout: 30000 });
await sleep(4100);

console.log("switch reviewer-2, same claim again (consensus)");
await smoothTo("#panel-sources");
await chooseWithCursor("reviewer-2");
await sleep(1400);
const card2 = page.locator(`#proposals article[data-item="${claimId}"]`);
if ((await card2.count()) > 0) {
  await card2.scrollIntoViewIfNeeded();
  await sleep(500);
  await clickWithCursor(`#proposals article[data-item="${claimId}"] [data-verdict='accept']`);
  await sleep(5300);
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
