# Guard-AI authentication setup

Guard-AI uses Supabase Auth for Google and anonymous sessions. The Google client
secret stays in Supabase; it must never be placed in the Vite frontend or
returned by `/api/v1/auth/config`.

## Supabase dashboard

1. Enable Google and paste the Google **client ID** and **client secret** into
   the Supabase Google provider settings.
2. In **URL Configuration**, set the Site URL to the production Guard-AI URL
   and allow both production and local redirects:
   - `https://guard-ai-secure-mcp.vercel.app/`
   - `http://127.0.0.1:5173/`
3. Enable anonymous sign-ins for the bounded guest demo.
4. Keep email confirmation enabled for any email/password flow. Google accounts
   arrive with a provider-verified email.
5. Keep CAPTCHA disabled only for local bring-up. Before a public launch,
   configure Turnstile or hCaptcha in Supabase and add its browser widget token
   to anonymous sign-in.
6. Prefer asymmetric JWT signing keys. Guard-AI supports JWKS validation for
   RS256/ES256 sessions and Auth-server validation for legacy HS256 sessions.

## Vercel environment

Configure these values for Production (and Preview if previews should sign in):

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_replace-me
GUARD_API_TOKEN_SECRET=replace-with-a-separate-random-32-character-secret
GUARD_GUEST_REQUEST_LIMIT=10
OPENROUTER_API_KEY=replace-me
GUARD_JUDGE_MODEL=replace-with-a-reliable-model-id
GUARD_SEMANTIC_JUDGE_ENABLED=true
```

`SUPABASE_ANON_KEY` is accepted as a compatibility fallback for the browser-safe
publishable key. Do not configure a Supabase service-role/secret key in a
browser-prefixed variable.

Generate distinct local secrets from one hidden seed using separate derivation
contexts:

```powershell
python scripts/generate_guard_token.py --purpose admin
python scripts/generate_guard_token.py --purpose api
```

## Access model

- Google-authenticated user: tenant-isolated connections, policies, traces, chat,
  and personal-token creation.
- Anonymous user: guarded simulation only, bounded by
  `GUARD_GUEST_REQUEST_LIMIT`; no connections, policies, traces, or tokens.
- Personal `gai_` token: the issuing user's workspace scopes until expiry.
- Legacy operator token: recovery access plus import of server-owned environment
  integrations.
