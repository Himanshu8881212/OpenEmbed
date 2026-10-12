import { auth } from "@/lib/auth";
import { tx } from "@/lib/db";
import { route } from "@/lib/http";
import { baseUrl, getStore, queryAlias } from "@/lib/stores";

/** Connection details + runnable snippets (the key is read from KNOWLEDGE_API_KEY; never embedded). */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "search");
    const alias = await queryAlias(db, s.profile_id);
    const base = baseUrl();
    const searchUrl = `${base}/v1/stores/${s.id}/search`;
    const python = `import os
import requests

response = requests.post(
    "${searchUrl}",
    headers={"Authorization": f"Bearer {os.environ['KNOWLEDGE_API_KEY']}"},
    json={"query": {"text": "How do I replace the pressure sensor?"}, "limit": 5},
    timeout=30,
)
response.raise_for_status()
for result in response.json()["results"]:
    print(result["score"], result["source"]["path"], result["source"]["location"])
    print(result["content"])
`;
    const javascript = `const response = await fetch("${searchUrl}", {
  method: "POST",
  headers: {
    Authorization: \`Bearer \${process.env.KNOWLEDGE_API_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ query: { text: "How do I replace the pressure sensor?" }, limit: 5 }),
  signal: AbortSignal.timeout(30000),
});
if (!response.ok) throw new Error(\`Search failed: \${response.status}\`);
const data = await response.json();
for (const r of data.results) console.log(r.score, r.source.path, r.source.location);
`;
    const curl = `curl -sS -X POST "${searchUrl}" \\
  -H "Authorization: Bearer $KNOWLEDGE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"query": {"text": "How do I replace the pressure sensor?"}, "limit": 5}'
`;
    const embeddings_python = `import os
from openai import OpenAI  # tested with openai==2.x / 7.x JS; text inputs only

client = OpenAI(base_url="${base}/v1", api_key=os.environ["KNOWLEDGE_API_KEY"])
vector = client.embeddings.create(model="${alias}", input="How do I replace the pressure sensor?").data[0].embedding
print(len(vector))
`;
    return {
      store_id: s.id, store_name: s.name, base_url: base, search_url: searchUrl, embeddings_base_url: `${base}/v1`,
      query_model: alias, profile_id: s.profile_id, index_revision: s.active_revision_id,
      required_scopes: ["search"], credential_env: "KNOWLEDGE_API_KEY",
      snippets: { python, javascript, curl, embeddings_python },
    };
  });
});
