import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import fs from "node:fs/promises";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const html = path.join(root, "src", "index.html");
const outputDir = path.join(root, "output");
const output = path.join(outputDir, "basefrom50-free-guide.pdf");

await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1200, height: 1697 },
  deviceScaleFactor: 1
});

await page.goto(pathToFileURL(html).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

const pageCount = await page.locator(".page").count();
if (pageCount !== 6) {
  throw new Error(`Expected 6 guide pages, found ${pageCount}`);
}

await page.pdf({
  path: output,
  format: "A4",
  printBackground: true,
  margin: { top: "0", right: "0", bottom: "0", left: "0" },
  preferCSSPageSize: true
});

await browser.close();
console.log(`Created: ${output}`);
