// Metrics are operational: scraped, valid on the dashboard, alerting rules correct, alerts delivered by email,
// and a real outage (no live workers) fires and resolves an alert end to end.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { after, before, describe, test } from "node:test";
import { ROOT, newStore, newWorkspace, owner, search, ingest, sleep, startWorker, stopAllWorkers } from "./helpers.mjs";

const PROM = "http://localhost:9090", AM = "http://localhost:9093", GRAFANA = "http://localhost:3001", MAIL = "http://localhost:8026";
const q = async (expr) => {
  const r = await (await fetch(`${PROM}/api/v1/query?query=${encodeURIComponent(expr)}`)).json();
  if (r.status !== "success") throw new Error(`${expr}: ${r.error}`);
  return r.data.result;
};
const value = async (expr) => Number((await q(expr))[0]?.value?.[1] ?? NaN);
async function until(fn, ms, what) {
  const end = Date.now() + ms;
  for (;;) { const v = await fn(); if (v) return v; if (Date.now() > end) throw new Error(`timed out waiting for ${what}`); await sleep(3000); }
}
const mails = async (needle) => (await (await fetch(`${MAIL}/api/v1/search?query=${encodeURIComponent(needle)}`)).json()).messages ?? [];

after(async () => { await stopAllWorkers(); await owner.end(); });

describe("metrics pipeline", () => {
  test("Prometheus scrapes the API and the inference service; all alert rules are loaded", async () => {
    const t = (await (await fetch(`${PROM}/api/v1/targets`)).json()).data.activeTargets;
    for (const job of ["kb-api", "kb-inference"]) assert.equal(t.find((x) => x.labels.job === job)?.health, "up", job);
    const rules = (await (await fetch(`${PROM}/api/v1/rules`)).json()).data.groups.flatMap((g) => g.rules);
    assert.deepEqual(rules.map((r) => r.name).sort(), ["KBApiDown", "KBHigh5xxRate", "KBInferenceDown", "KBInferenceSaturated", "KBJobItemFailures", "KBQueueBacklog", "KBQueueStalled", "KBSlowSearch", "KBWorkersDown"]);
    assert.ok(rules.every((r) => r.health === "ok"), "every rule evaluates without error");
  });
  test("alert rule unit tests (promtool) pass", () => {
    const out = execFileSync("docker", ["compose", "exec", "-T", "prometheus", "promtool", "test", "rules", "/etc/prometheus/rules.test.yml"], { cwd: ROOT, encoding: "utf8" });
    assert.match(out, /SUCCESS/);
  });
  test("real traffic shows up: API request counters and inference throughput by modality", async () => {
    startWorker();
    const W = await newWorkspace("alice");
    const s = await newStore(W);
    await ingest(W, s.id, [{ path: "obs.txt", data: Buffer.from("Observability check: pump bearings are greased monthly.") }]);
    const before = (await value('sum(kb_inference_inputs_total{modality="text"})')) || 0;
    for (let i = 0; i < 3; i++) await search(W, s.id, `pump bearing grease ${i}`);
    await until(async () => (await value('sum(kb_inference_inputs_total{modality="text"})')) >= before + 3, 60_000, "inference counters to be scraped");
    await until(async () => (await value('sum(kb_http_requests_total{route="/v1/stores/:id/search",status="200"})')) >= 3, 60_000, "search request counter");
    assert.ok((await value("max(kb_segments)")) > 0);
    await stopAllWorkers();
  });
  test("every Grafana panel query is valid PromQL and the provisioned dashboard serves data", async () => {
    const dash = JSON.parse(readFileSync(`${ROOT}infra/observability/grafana/dashboards/knowledge-store.json`, "utf8"));
    for (const p of dash.panels) for (const t of p.targets) await q(t.expr); // throws on invalid PromQL
    const g = await (await fetch(`${GRAFANA}/api/dashboards/uid/knowledge-store`)).json();
    assert.equal(g.dashboard.panels.length, dash.panels.length);
    const r = await fetch(`${GRAFANA}/api/ds/query`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ from: "now-5m", to: "now", queries: [{ refId: "A", datasource: { uid: "prometheus" }, expr: 'max(up{job="kb-api"})', instant: true }] }) });
    const j = await r.json();
    assert.equal(r.status, 200, JSON.stringify(j).slice(0, 200));
    assert.equal(j.results.A.frames[0].data.values[1][0], 1, "Grafana reads the API up metric through the datasource");
  });
  test("Alertmanager delivers alerts by email", async () => {
    const name = `KBDeliveryCheck${Date.now()}`;
    const r = await fetch(`${AM}/api/v2/alerts`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify([{ labels: { alertname: name, severity: "info" }, annotations: { summary: "delivery check" } }]) });
    assert.equal(r.status, 200);
    await until(async () => (await mails(name)).length > 0, 90_000, "alert email in Mailpit");
  });
});

describe("live outage → alert → resolution", () => {
  test("no live workers fires KBWorkersDown and emails ops; starting a worker resolves it", async (t) => {
    await stopAllWorkers();
    // external workers (e.g. a developer's) make this condition impossible to create; CI has none
    const alive = await until(async () => { const v = await value("max(kb_workers_alive)"); return v === 0 ? "none" : null; }, 150_000, "worker heartbeats to expire").catch(() => "external");
    if (alive === "external") return t.skip("another worker process is alive outside the test; cannot simulate the outage");
    const firing = await until(async () => (await q('ALERTS{alertname="KBWorkersDown",alertstate="firing"}')).length > 0, 180_000, "KBWorkersDown to fire");
    assert.ok(firing);
    await until(async () => (await mails("KBWorkersDown")).length > 0, 90_000, "KBWorkersDown email");
    startWorker();
    await until(async () => (await q('ALERTS{alertname="KBWorkersDown"}')).length === 0, 180_000, "KBWorkersDown to resolve");
    await stopAllWorkers();
  });
});
