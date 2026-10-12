// Web workbench journeys in a real browser (Chromium via Playwright) against the real API, IdP, storage and model.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, test } from "node:test";
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
import { BASE, owner, startWorker, stopAllWorkers } from "./helpers.mjs";

let browser, page;
const dir = mkdtempSync(join(tmpdir(), "kb-web-"));
const folder = join(dir, "company-material");

async function axe(label) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  assert.deepEqual(bad.map((v) => `${v.id}: ${v.nodes[0]?.target}`), [], `${label} accessibility`);
}

before(async () => {
  startWorker();
  mkdirSync(join(folder, "manuals"), { recursive: true });
  writeFileSync(join(folder, "manuals/pressure.md"), "# Pressure sensor\n\nTo replace the pressure sensor remove the four M6 bolts and disconnect connector P7, then run CAL-22.");
  writeFileSync(join(folder, "canteen.txt"), "The canteen serves lunch from 11:30 to 14:00.");
  writeFileSync(join(folder, ".DS_Store"), "x");
  writeFileSync(join(folder, "setup.exe"), "MZ");
  // fresh identity state for the journey user
  await owner.query("DELETE FROM members WHERE email = 'dave@example.com'");
  browser = await chromium.launch();
  page = await (await browser.newContext({ baseURL: BASE, reducedMotion: "reduce" })).newPage(); // axe measures settled (non-animated) colours
});
after(async () => { await browser?.close(); await stopAllWorkers(); await owner.end(); rmSync(dir, { recursive: true, force: true }); });

describe("device authorization flow (CLI login) with real browser approval", () => {
  test("device session → user approves in the IdP → /v1/auth/token returns tokens → /v1/me", async () => {
    const d = await (await fetch(`${BASE}/v1/auth/device-sessions`, { method: "POST" })).json();
    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await p.goto(d.verification_uri_complete);
    await p.fill("#username", "carol@example.com");
    await p.fill("#password", "dev-carol-password");
    await p.click("#kc-login");
    const yes = p.locator('input[name="accept"], #kc-login');
    await yes.first().click();
    await p.waitForLoadState();
    await ctx.close();
    let tok;
    for (let i = 0; i < 20 && !tok; i++) {
      const r = await fetch(`${BASE}/v1/auth/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ grant_type: "device_code", device_code: d.device_code }) });
      const j = await r.json();
      if (r.ok) tok = j; else { assert.equal(j.error.code, "AUTHORIZATION_PENDING"); await new Promise((x) => setTimeout(x, (d.interval || 1) * 1000)); }
    }
    assert.ok(tok?.access_token && tok.refresh_token);
    const me = await (await fetch(`${BASE}/v1/me`, { headers: { authorization: `Bearer ${tok.access_token}` } })).json();
    assert.equal(me.email, "carol@example.com");
    const refreshed = await fetch(`${BASE}/v1/auth/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ grant_type: "refresh_token", refresh_token: tok.refresh_token }) });
    assert.equal(refreshed.status, 200);
  });
});

describe("self-registration with email verification", () => {
  test("Register → verification mail → link signs the new user in → onboarding", async () => {
    const email = `signup-${Date.now()}@example.com`;
    const ctx = await browser.newContext({ baseURL: BASE, reducedMotion: "reduce" });
    const p = await ctx.newPage();
    await p.goto("/");
    await p.waitForURL(/realms\/kb/);
    await p.getByRole("link", { name: "Register" }).click();
    await p.fill("#email", email);
    await p.fill("#password", "correct-horse-battery");
    await p.fill("#password-confirm", "correct-horse-battery");
    if (await p.locator("#firstName").count()) { await p.fill("#firstName", "New"); await p.fill("#lastName", "User"); }
    await p.getByRole("button", { name: /Register/i }).click();
    await p.getByText(/verify your email/i).first().waitFor();
    let link;
    for (let i = 0; i < 40 && !link; i++) {
      const list = await (await fetch("http://localhost:8026/api/v1/messages")).json();
      const m = list.messages.find((x) => x.To.some((t) => t.Address === email));
      if (m) link = /(http:\/\/localhost:8180\/realms\/kb\/login-actions\/action-token[^\s"<>]+)/.exec((await (await fetch(`http://localhost:8026/api/v1/message/${m.ID}`)).json()).Text)?.[1];
      else await new Promise((r) => setTimeout(r, 500));
    }
    assert.ok(link, "verification email delivered");
    await p.goto(link);
    await p.waitForURL(`${BASE}/**`);
    await p.getByRole("heading", { name: "Set up your workspace" }).waitFor();
    await p.getByText(`Signed in as ${email}`).waitFor();
    await ctx.close();
  });
  test("weak passwords are rejected by the provider policy", async () => {
    const ctx = await browser.newContext({ baseURL: BASE });
    const p = await ctx.newPage();
    await p.goto("/");
    await p.waitForURL(/realms\/kb/);
    await p.getByRole("link", { name: "Register" }).click();
    await p.fill("#email", `weak-${Date.now()}@example.com`);
    await p.fill("#password", "short");
    await p.fill("#password-confirm", "short");
    if (await p.locator("#firstName").count()) { await p.fill("#firstName", "W"); await p.fill("#lastName", "K"); }
    await p.getByRole("button", { name: /Register/i }).click();
    await p.getByText(/Invalid password|minimum length/i).first().waitFor();
    await ctx.close();
  });
});

describe("web workbench", () => {
  let secret;
  test("first screen is the sign-in form (no extra landing page); sign in with code + PKCE", async () => {
    await page.goto("/");
    await page.waitForURL(/realms\/kb\/protocol\/openid-connect\/auth/);
    await axe("sign-in form");
    await page.fill("#username", "dave@example.com");
    await page.fill("#password", "dev-dave-password");
    await page.click("#kc-login");
    await page.waitForURL(`${BASE}/`);
    await page.getByText("Signed in as dave@example.com").waitFor();
  });
  test("workspace name is pre-filled with a readable random name; dice suggests another", async () => {
    const field = page.getByLabel("Workspace name", { exact: true });
    const first = await field.inputValue();
    assert.match(first, /^[A-Z][a-z]+ [A-Z][a-z]+$/);
    await page.getByRole("button", { name: "Suggest another workspace name" }).click();
    await field.fill("Web Co");
  });
  test("create a workspace and a store (empty state, then list)", async () => {
    await page.getByRole("button", { name: "Create workspace" }).click();
    await page.getByRole("heading", { name: "Stores" }).waitFor();
    await page.getByRole("form", { name: "New store" }).waitFor();
    assert.match(await page.getByLabel("Store name", { exact: true }).inputValue(), /^[a-z]+-[a-z]+-\d{2}$/, "store name pre-filled");
    await page.getByLabel("Store name", { exact: true }).fill("web-manuals");
    await page.getByRole("button", { name: "Create store" }).click();
    await page.locator("a.store-card", { hasText: "web-manuals" }).click();
    await page.getByRole("heading", { name: /web-manuals/ }).waitFor();
    await axe("store page");
  });
  test("tabs are keyboard operable", async () => {
    const search = page.getByRole("tab", { name: "Search" });
    await search.focus();
    await page.keyboard.press("ArrowRight");
    assert.equal(await page.getByRole("tab", { name: "Files" }).getAttribute("aria-selected"), "true");
    await page.getByText("No files in this store yet").waitFor();
    await page.keyboard.press("End");
    assert.equal(await page.getByRole("tab", { name: "Settings" }).getAttribute("aria-selected"), "true");
  });
  test("folder import uploads real bytes, lists ignored files, and shows job progress to completion", async () => {
    await page.getByRole("tab", { name: "Import" }).click();
    await page.getByLabel("Folder to import").setInputFiles(folder);
    await page.getByText("2 file(s) to upload").waitFor();
    await page.getByText("Ignored files").click();
    await page.getByText("setup.exe — unsupported format").waitFor();
    await page.getByRole("button", { name: /Upload and index 2 file/ }).click();
    await page.locator('[role="tab"][aria-selected="true"]', { hasText: "Jobs" }).waitFor({ timeout: 60_000 });
    await page.getByText(/2 of 2 items succeeded/).waitFor({ timeout: 120_000 });
    await page.locator('[data-state="completed"]').first().waitFor();
  });
  test("search shows evidence with source path, version and location", async () => {
    await page.getByRole("tab", { name: "Search" }).click();
    await page.getByLabel("Question or keywords").fill("How do I replace the pressure sensor?");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const first = page.locator("li.result").first();
    await first.getByRole("heading", { name: /manuals\/pressure\.md/ }).waitFor();
    assert.match(await first.innerText(), /v1[\s\S]*¶ 0–\d+[\s\S]*relevance 0\.\d{3}/);
    await axe("search results");
  });
  test("inspect a file and edit metadata", async () => {
    await page.getByRole("tab", { name: "Files" }).click();
    await page.getByRole("button", { name: "Inspect manuals/pressure.md" }).click();
    await page.getByText(/manuals\/pressure\.md — published/).waitFor();
    await page.getByLabel("Key").fill("department");
    await page.getByLabel("Value").fill("service");
    await page.getByRole("button", { name: "Set metadata" }).click();
    await page.getByText("department = service").waitFor();
    await axe("file drawer");
    await page.keyboard.press("Escape");
  });
  test("connection modal: details, code tabs, one-time key; Escape closes", async () => {
    await page.getByRole("button", { name: "Connect application" }).click();
    const dlg = page.getByRole("dialog", { name: /Connect an application to web-manuals/ });
    await dlg.getByText("Query model alias").waitFor();
    assert.match(await dlg.getByLabel("Python code", { exact: true }).innerText(), /requests\.post/);
    await dlg.getByRole("tab", { name: "Python" }).focus();
    await page.keyboard.press("ArrowRight");
    assert.match(await dlg.getByLabel("JavaScript code", { exact: true }).innerText(), /fetch\(/);
    await dlg.getByRole("button", { name: "Create a search key for this store" }).click();
    secret = (await dlg.locator(".secret").innerText()).trim();
    assert.match(secret, /^kb_/);
    await axe("connection dialog");
    await page.keyboard.press("Escape");
    assert.equal(await dlg.isVisible(), false);
  });
  test("no permanent credential is kept in browser storage", async () => {
    const stored = await page.evaluate(() => JSON.stringify({ ...sessionStorage }) + JSON.stringify({ ...localStorage }) + document.cookie);
    assert.ok(!stored.includes(secret));
    assert.ok(!/kb_[A-Za-z0-9_-]{20,}/.test(stored));
    // the key works from a backend, as the guide intends
    const r = await fetch(`${BASE}/v1/stores?limit=1`, { headers: { authorization: `Bearer ${secret}` } });
    assert.equal(r.status, 200);
  });
  test("connector: add, sync now, job completes, file appears", async () => {
    const srv = createServer((req, res) => res.end(req.url === "/manifest.json" ? JSON.stringify({ files: [{ path: "synced/hours.txt", url: "hours.txt" }] }) : "Reception is staffed from 08:00 to 18:00.")).listen(8765, "127.0.0.1");
    await new Promise((ok, fail) => (srv.listening ? ok() : srv.once("listening", ok).once("error", fail)));
    try {
      await page.getByRole("tab", { name: "Composition" }).click();
      await page.getByLabel("Manifest URL").fill("http://127.0.0.1:8765/manifest.json");
      await page.getByRole("button", { name: "Add connector" }).click();
      await page.getByRole("button", { name: /Sync now/ }).click();
      await page.locator('[role="tab"][aria-selected="true"]', { hasText: "Jobs" }).waitFor();
      const done = page.locator('.card [data-state="completed"], .card [data-state="failed"]').first();
      await done.waitFor({ timeout: 120_000 });
      assert.equal(await done.getAttribute("data-state"), "completed");
      await page.getByText(/1 of 1 items succeeded/).waitFor();
      await page.getByRole("tab", { name: "Files" }).click();
      await page.getByRole("button", { name: "Inspect synced/hours.txt" }).waitFor();
      await axe("composition + connectors");
    } finally { srv.close(); }
  });
  test("error state for a missing store; usage and keys pages", async () => {
    await page.goto("/stores/00000000-0000-4000-8000-000000000000");
    await page.getByRole("alert").filter({ hasText: "Store not found" }).waitFor();
    await page.goto("/settings");
    await page.getByText(/Storage: .* of /).waitFor();
    await axe("usage page");
    await page.getByRole("tab", { name: "API keys" }).click();
    await page.getByRole("button", { name: /Revoke web-manuals-app/ }).click();
    await page.getByRole("cell", { name: "revoked" }).waitFor();
  });
});
