// The published OpenAPI document and the implemented route handlers must match exactly (no undocumented or phantom endpoints).
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { test } from "node:test";
import { api, ROOT } from "./helpers.mjs";

function routes(dir = `${ROOT}app/v1`, prefix = "/v1") {
  const out = [];
  for (const n of readdirSync(dir)) {
    const abs = `${dir}/${n}`;
    if (statSync(abs).isDirectory()) out.push(...routes(abs, `${prefix}/${n.replace(/^\[(.+)\]$/, "{$1}")}`));
    else if (n === "route.ts") for (const m of readFileSync(abs, "utf8").matchAll(/export (?:const|async function) (GET|POST|PUT|PATCH|DELETE)\b/g)) out.push(`${m[1].toLowerCase()} ${prefix}`);
  }
  return out;
}

test("every route is documented in OpenAPI and every documented operation exists", async () => {
  const r = await api(null, "GET", "/v1/openapi.json");
  assert.equal(r.status, 200);
  assert.equal(r.body.openapi, "3.1.0");
  const documented = Object.entries(r.body.paths).flatMap(([p, ops]) => Object.keys(ops).map((m) => `${m} ${p}`)).sort();
  assert.deepEqual(routes().sort(), documented);
  const refs = JSON.stringify(r.body).match(/#\/components\/schemas\/\w+/g).map((x) => x.split("/").pop());
  for (const s of new Set(refs)) assert.ok(r.body.components.schemas[s], `missing schema ${s}`);
});

test("validated format list is identical in the API and the worker", () => {
  const ts = Object.fromEntries([...readFileSync(`${ROOT}lib/formats.ts`, "utf8").matchAll(/"(\.\w+)": \{ media_type: "([^"]+)"/g)].map((m) => [m[1], m[2]]));
  const py = Object.fromEntries([...readFileSync(`${ROOT}py/kbpy/jobs.py`, "utf8").match(/FORMATS = \{([\s\S]*?)\}/)[1].matchAll(/"(\.\w+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]));
  assert.ok(Object.keys(ts).length >= 10);
  assert.deepEqual(py, ts);
});
