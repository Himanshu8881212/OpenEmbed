// Resource/latency measurement against the local stack (real model). Usage: node scripts/measure.mjs
import { existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
if (existsSync(".env")) process.loadEnvFile(".env"); // optional: containers use real environment variables
const INF = process.env.KB_INFERENCE_URL, H = { authorization: `Bearer ${process.env.KB_INFERENCE_TOKEN}`, "content-type": "application/json" };
const profile = { model: "google/embeddinggemma-2", revision: "914f7f89142e33e77833254d9c9b90c3cef7303b", dtype: process.env.KB_INFERENCE_DTYPE ?? "float32" };
const b64 = (p) => readFileSync(p).toString("base64");
async function time(label, inputs, n = 3) {
  const ms = [];
  let tokens = 0;
  for (let i = 0; i < n; i++) {
    const t = performance.now();
    const r = await fetch(`${INF}/embed`, { method: "POST", headers: H, body: JSON.stringify({ profile, inputs }) });
    const j = await r.json();
    ms.push(performance.now() - t);
    tokens = j.data.reduce((a, d) => a + d.tokens, 0);
  }
  ms.sort((a, b) => a - b);
  console.log(`${label.padEnd(44)} median ${ms[Math.floor(n / 2)].toFixed(0).padStart(6)} ms  (${tokens} tokens)`);
}
const passage = "The maintenance log records inspection of valve V12 and pump P3, noting seal wear and lubricant level. ".repeat(15).slice(0, 1600);
execSync("ffmpeg -v error -y -f lavfi -i sine=frequency=300:duration=30 -ar 16000 -ac 1 /tmp/kb-30s.wav && ffmpeg -v error -y -f lavfi -i testsrc=duration=30:size=640x480:rate=1 -pix_fmt yuv420p /tmp/kb-30s.mp4");
await time("query text (1 short input)", [{ parts: [{ type: "text", text: "task: search result | query: replace the pressure sensor" }] }], 7);
await time("document text batch (16 × 1600 chars)", Array.from({ length: 16 }, () => ({ parts: [{ type: "text", text: passage }] })));
await time("image (PNG 256×256, 280 soft tokens)", [{ parts: [{ type: "image", data_b64: b64("tests/fixtures/corpus/media/red-square.png") }] }]);
await time("audio 30 s (16 kHz mono)", [{ parts: [{ type: "audio", data_b64: b64("/tmp/kb-30s.wav") }] }]);
await time("video 30 s (1 fps, 30 frames)", [{ parts: [{ type: "video", data_b64: b64("/tmp/kb-30s.mp4") }] }]);
const rss = (pat) => { try { return execSync(`ps -axo rss,command | grep -E "${pat}" | grep -v grep | awk '{s+=$1} END {print s}'`).toString().trim(); } catch { return "?"; } };
console.log(`RSS inference ${(rss("kbpy.inference") / 1024).toFixed(0)} MiB, worker ${(rss("kbpy.worker") / 1024).toFixed(0)} MiB, next ${(rss("next-server|next dev") / 1024).toFixed(0)} MiB`);
console.log(execSync(`docker compose exec -T postgres psql -U kb_owner kb -Atc "select 'db size ' || pg_size_pretty(pg_database_size('kb')) || ', segments ' || (select count(*) from segments)"`).toString().trim());
