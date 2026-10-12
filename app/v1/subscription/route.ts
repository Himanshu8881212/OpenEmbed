import { auth, require_ } from "@/lib/auth";
import { tx } from "@/lib/db";
import { route } from "@/lib/http";
import { plan } from "@/lib/usage";

/** Plan and allowances. No payment provider is configured; prices are not part of this build. */
export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "usage");
  return tx(p.workspaceId, async (db) => ({ plan: await plan(db), payment_provider: process.env.KB_PAYMENT_PROVIDER || null, change_plan_url: null }));
});
