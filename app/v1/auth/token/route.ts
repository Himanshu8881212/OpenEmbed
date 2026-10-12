import { z } from "zod";
import { config } from "@/lib/config";
import { ApiError, body, route } from "@/lib/http";

const Req = z.discriminatedUnion("grant_type", [
  z.object({ grant_type: z.literal("device_code"), device_code: z.string().min(1) }),
  z.object({ grant_type: z.literal("refresh_token"), refresh_token: z.string().min(1) }),
]);

/** Exchange an authorised device session (or refresh token) for tokens. Pending authorisation → 400 authorization_pending. */
export const POST = route(async (req) => {
  const b = await body(req, Req);
  const c = config();
  const form = new URLSearchParams({ client_id: c.KB_OIDC_CLI_CLIENT_ID });
  if (b.grant_type === "device_code") { form.set("grant_type", "urn:ietf:params:oauth:grant-type:device_code"); form.set("device_code", b.device_code); }
  else { form.set("grant_type", "refresh_token"); form.set("refresh_token", b.refresh_token); }
  const r = await fetch(`${c.KB_OIDC_ISSUER}/protocol/openid-connect/token`, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: form }).catch(() => null);
  if (!r) throw new ApiError(503, "SERVICE_UNAVAILABLE", "The identity provider is unavailable");
  const j = await r.json();
  if (!r.ok) {
    const code = String(j.error ?? "invalid_grant");
    if (code === "authorization_pending" || code === "slow_down") throw new ApiError(400, code.toUpperCase(), "Authorisation is still pending");
    if (code === "expired_token") throw new ApiError(400, "EXPIRED_TOKEN", "The device session expired; start a new one");
    throw new ApiError(401, "AUTHENTICATION_REQUIRED", "The grant was rejected");
  }
  return { access_token: j.access_token, refresh_token: j.refresh_token, token_type: "Bearer", expires_in: j.expires_in };
});
