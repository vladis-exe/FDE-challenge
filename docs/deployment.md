# Deploying to Railway

What app lane already worked out (`status/app.md`), consolidated into one sequence. The
`Dockerfile`/`docker-compose.yml` (A8) are already built and smoke-tested against Postgres —
this is about wiring them into Railway, not building anything new.

## 1. Create the project

In Railway: new project → deploy from this GitHub repo. Add a **Postgres** plugin to the
project — it sets `DATABASE_URL` on anything attached to it automatically.

## 2. Two services, one image

Railway builds the `Dockerfile` once; both services below point at that same build.

| Service | Start command | Replicas | Notes |
| --- | --- | --- | --- |
| **web** | (the image's default `CMD` — gunicorn on `$PORT`) | 1+ | Release/pre-deploy command: `python manage.py migrate --noinput`. Healthcheck path: `/healthz`. |
| **worker** | `python manage.py run_worker` | **exactly 1** | More than one is safe on Postgres (`skip_locked`), but one is enough at this scale; don't pay for more. |

## 3. Environment variables (set on both services)

```
DATABASE_URL              # from the Postgres plugin, not set by hand
DJANGO_SECRET_KEY         # long random string, generate fresh, don't reuse the dev one
DEBUG=False
ALLOWED_HOSTS=<app>.up.railway.app
PUBLIC_BASE_URL=https://<app>.up.railway.app   # exact: CSRF trust and the Twilio signature check both depend on this matching precisely
ANTHROPIC_API_KEY
LLM_MODEL_FAST=claude-haiku-5-5
LLM_MODEL_SMART=claude-sonnet-5-5              # the real config — don't ship the dev budget override (see .env's comment on LLM_MODEL_SMART)
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM
WHATSAPP_VACANCY=driver                        # optional; which job a bare WhatsApp message (no link) screens for
DEMO_TIME_SCALE=1                              # real timing in production; raise it temporarily for a live reminder demo
DEMO_RECRUITER_PASSWORD                        # optional; seed_demo generates one and prints it if unset
```

Leave `SECURE_COOKIES` unset — it defaults on, which is what you want in production.

## 4. First deploy

The release command runs `migrate` automatically on every deploy, so the schema's current the
moment it's live. Then, once:

```bash
railway run python manage.py seed_demo      # recruiter login + 24 real demo conversations
railway run python manage.py createsuperuser  # for /admin/, separate from the dashboard login
```

`seed_demo --reset` replaces **all** data — only run it again if you deliberately want a clean
slate, not routinely.

## 5. Smoke test

Hit these on the deployed URL: `/healthz`, `/chat/?vacancy=driver`, `/apply/`, `/dashboard/`
(login with whatever `seed_demo` printed or generated). All should return real pages, not 500s.

`manage.py check --deploy` will flag W004 (no HSTS) and W008 (no SSL redirect) — **leave both**.
Railway terminates HTTPS at its edge; an app-level HTTPS redirect would also bounce Railway's
own plain-HTTP healthcheck, breaking deploys in a more confusing way than the warnings being
visible.

## 6. Twilio webhook — same limitation as local testing

Point the sandbox's webhook at `https://<app>.up.railway.app/webhooks/twilio/whatsapp/` (POST)
— but on a **free Twilio account this field isn't configurable at all** (confirmed via their
own API, D35); it redirects to an upgrade page regardless of what URL you'd set. A real deploy
doesn't change that. If the account gets upgraded, this is the one step to redo; nothing else
in this guide depends on it.

## Rollback

Railway keeps previous deploys; redeploying an older one is a dashboard action, not a `git`
operation here. If a bad migration ever ships, `python manage.py migrate <app> <previous>` via
`railway run` is the one to reach for — there's no destructive-migration story beyond Django's
own, since nothing here does manual schema surgery.
