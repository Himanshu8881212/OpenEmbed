import { config } from "@/lib/config";
import { ApiError, route } from "@/lib/http";

/** Start an OAuth 2.0 device authorization (RFC 8628) with the configured identity provider. */
export const POST = route(async () => {
  const c = config();
  const r = await fetch(`${c.KB_OIDC_ISSUER}/protocol/openid-connect/auth/device`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: c.KB_OIDC_CLI_CLIENT_ID, scope: "openid email" }),
  }).catch(() => null);
  if (!r?.ok) throw new ApiError(503, "SERVICE_UNAVAILABLE", "The identity provider is unavailable");
  const j = await r.json();
  return { device_code: j.device_code, user_code: j.user_code, verification_uri: j.verification_uri, verification_uri_complete: j.verification_uri_complete, expires_in: j.expires_in, interval: j.interval ?? 5 };
});
