"use client";
// Browser sign-in: OAuth 2.0 Authorization Code + PKCE (S256) against the OIDC provider's public `kb-web` client.
// Only short-lived user tokens are held, in sessionStorage (tab-scoped). Permanent API keys never live in the browser.
const ISSUER = process.env.NEXT_PUBLIC_KB_OIDC_ISSUER ?? "";
const CLIENT = process.env.NEXT_PUBLIC_KB_OIDC_WEB_CLIENT_ID ?? "kb-web";
type Tokens = { access_token: string; refresh_token?: string; id_token?: string; expires_at: number };

const b64url = (b: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(b as ArrayBuffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const redirectUri = () => `${location.origin}/callback`;

/** Start sign-in; `create` opens the provider's registration form (OIDC prompt=create). */
export async function login(opts: { create?: boolean } = {}) {
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = b64url(crypto.getRandomValues(new Uint8Array(16)));
  sessionStorage.setItem("kb.pkce", JSON.stringify({ verifier, state, back: location.pathname + location.search }));
  const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  const q = new URLSearchParams({ response_type: "code", client_id: CLIENT, redirect_uri: redirectUri(), scope: "openid email", code_challenge: challenge, code_challenge_method: "S256", state, ...(opts.create ? { prompt: "create" } : {}) });
  location.assign(`${ISSUER}/protocol/openid-connect/auth?${q}`);
}

async function tokenRequest(form: Record<string, string>) {
  const r = await fetch(`${ISSUER}/protocol/openid-connect/token`, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ client_id: CLIENT, ...form }) });
  if (!r.ok) throw new Error("Sign-in failed. Please sign in again.");
  const j = await r.json();
  const prev: Tokens | null = JSON.parse(sessionStorage.getItem("kb.tokens") ?? "null");
  const t: Tokens = { access_token: j.access_token, refresh_token: j.refresh_token, id_token: j.id_token ?? prev?.id_token, expires_at: Date.now() + j.expires_in * 1000 };
  sessionStorage.setItem("kb.tokens", JSON.stringify(t));
  return t;
}

/** Completes the redirect; returns the path to go back to. */
export async function completeLogin(params: URLSearchParams) {
  const saved = JSON.parse(sessionStorage.getItem("kb.pkce") ?? "null");
  sessionStorage.removeItem("kb.pkce");
  if (!saved || params.get("state") !== saved.state || !params.get("code")) throw new Error("Sign-in could not be verified. Please try again.");
  await tokenRequest({ grant_type: "authorization_code", code: params.get("code")!, redirect_uri: redirectUri(), code_verifier: saved.verifier });
  return saved.back || "/";
}

export function signedIn() { return typeof window !== "undefined" && !!sessionStorage.getItem("kb.tokens"); }

export async function accessToken(): Promise<string | null> {
  const t: Tokens | null = JSON.parse(sessionStorage.getItem("kb.tokens") ?? "null");
  if (!t) return null;
  if (Date.now() < t.expires_at - 30_000) return t.access_token;
  if (!t.refresh_token) return null;
  try { return (await tokenRequest({ grant_type: "refresh_token", refresh_token: t.refresh_token })).access_token; } catch { forget(); return null; }
}

/** Ends the session at the identity provider too (RP-initiated logout), then returns to the app's sign-in. */
export function logout() {
  const t: Tokens | null = JSON.parse(sessionStorage.getItem("kb.tokens") ?? "null");
  sessionStorage.removeItem("kb.tokens");
  const q = new URLSearchParams({ client_id: CLIENT, post_logout_redirect_uri: `${location.origin}/`, ...(t?.id_token ? { id_token_hint: t.id_token } : {}) });
  location.assign(`${ISSUER}/protocol/openid-connect/logout?${q}`);
}
/** Drop local tokens only (expired session); the next page load signs in again. */
export function forget() { sessionStorage.removeItem("kb.tokens"); }
