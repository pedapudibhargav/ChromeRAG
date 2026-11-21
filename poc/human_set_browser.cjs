// Load one page with Playwright 1.55.1 in installed Chrome and print status, final address and HTML as JSON.
// Usage: PLAYWRIGHT_MODULE=<path to playwright> node human_set_browser.cjs <url> <allowed hosts, comma separated> <scripts 1|0> <user agent>
// Only the allowed hosts and their subdomains are ever contacted; images, media and fonts never load.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const [url, hostList, scripts, userAgent] = process.argv.slice(2);
const hosts = hostList.split(",");
const allowed = (h) => hosts.some((a) => h === a || h.endsWith("." + a));
const rules = ["MAP * ~NOTFOUND", ...hosts.flatMap((h) => [`EXCLUDE ${h}`, `EXCLUDE *.${h}`])].join(", ");

(async () => {
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
    args: [`--host-resolver-rules=${rules}`, "--disable-background-networking", "--disable-component-update", "--disable-sync"],
  });
  const out = {};
  try {
    const context = await browser.newContext({
      userAgent,
      javaScriptEnabled: scripts !== "0",
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    const blocked = new Set();
    await page.route("**/*", (route) => {
      const request = route.request();
      const host = new URL(request.url()).hostname.toLowerCase();
      const heavy = ["image", "media", "font"].includes(request.resourceType());
      if (allowed(host) && !heavy) return route.continue();
      if (!heavy) blocked.add(host);
      return route.abort("blockedbyclient");
    });
    const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (scripts !== "0") {
      await page.waitForTimeout(2000);
      await page.waitForSelector("main, article, [role='main']", { timeout: 8000, state: "visible" }).catch(() => {});
      const top = await page.evaluate("document.body ? document.body.scrollHeight : 0");
      for (let y = 0; y < Math.min(top, 20000); y += 900) {
        await page.evaluate(`window.scrollTo(0, ${y})`);
        await page.waitForTimeout(200);
      }
      await page.waitForTimeout(1000);
    }
    Object.assign(out, {
      status: response ? response.status() : 0,
      final_url: page.url(),
      html: await page.content(),
      blocked_hosts: [...blocked].sort(),
    });
  } catch (error) {
    out.error = String(error);
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out), () => process.exit(out.error ? 1 : 0));
})();
