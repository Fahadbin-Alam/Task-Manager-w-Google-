<!-- Author: Fahadbin Alam (fma52), 4/19/26 -->
<!-- Mod by Codex, 4/19/26 -->
<!-- From One World Relief donation backend integration, 4/19/26 -->
# One World Relief Backend Setup

## What this backend now does
- Stores donors in SQLite (`charity_donors`)
- Stores donation transactions with date and status (`charity_donations`)
- Auto-generates receipts after successful payment (`charity_receipts`)
- Stores an audit log for payment events (`charity_audit_logs`)
- Supports checkout creation for:
  - PayPal
  - Credit card (via Stripe Checkout)
  - Stripe
- Supports tax CSV export by date/status/email

## Local runtime
Use Python 3.11 for the backend. The Dockerfile already uses Python 3.11.

This local machine currently has Python 3.14, which can fail while installing pinned FastAPI/Pydantic dependencies because some native wheels are not available for that version yet.

## Required env vars (payment providers)
- `OWR_STRIPE_SECRET_KEY` - your Stripe secret key from the Stripe Dashboard
- `OWR_STRIPE_WEBHOOK_SECRET` - your Stripe webhook signing secret for `/charity/webhooks/stripe`
- `OWR_PAYPAL_CLIENT_ID`
- `OWR_PAYPAL_CLIENT_SECRET`
- `OWR_PAYPAL_BASE_URL` (default sandbox)
- `OWR_SUCCESS_URL` (default: `http://localhost:8000/charity/thank-you`)
- `OWR_CANCEL_URL` (default: `http://localhost:8000/charity/cancelled`)
- `OWR_ADMIN_API_KEY` (optional but recommended for tax/report endpoints)

## Stripe setup checklist
1. In Stripe, use Checkout Sessions for One World Relief donations.
2. Put your test secret key in `OWR_STRIPE_SECRET_KEY`.
3. Add a webhook endpoint pointing to:
   - Local testing with Stripe CLI: `http://localhost:8000/charity/webhooks/stripe`
   - Deployed site: `https://your-domain.com/charity/webhooks/stripe`
4. Listen for these events:
   - `checkout.session.completed`
   - `checkout.session.expired`
   - `payment_intent.payment_failed`
5. Put the webhook signing secret in `OWR_STRIPE_WEBHOOK_SECRET`.
6. Set `OWR_SUCCESS_URL` and `OWR_CANCEL_URL` to your real deployed domain before going live.

The frontend never collects card numbers. Donors are redirected to Stripe-hosted Checkout.

## API endpoints added
- `POST /charity/donations/checkout`
- `POST /charity/paypal/capture/{order_id}`
- `POST /charity/webhooks/stripe`
- `POST /charity/webhooks/paypal`
- `POST /charity/donations/{donation_id}/mock-complete` (admin/testing)
- `GET /charity/donations` (admin)
- `GET /charity/donations/export.csv` (admin)
- `GET /charity/receipts/{receipt_number}` (admin)

## Frontend page routes
- `GET /charity`
- `GET /charity/index.html`
- `GET /charity/about.html`
- `GET /charity/projects.html`
- `GET /charity/donate.html`
- `GET /charity/contact.html`
- `GET /one-world-relief.css`
- `GET /one-world-relief.js`
- `GET /project-data.js`

## Adding project photos and videos
Project cards are powered by `project-data.js`. To add a new project, create a new object with:
- `title`
- `category`
- `status`
- `location`
- `date`
- `amountRaised`
- `impact`
- `summary`
- `update`
- `thumbnailUrl`
- `mediaUrl`
- `donationUrl`

For videos, the easiest workflow is to upload to YouTube as public or unlisted and paste the video URL into `mediaUrl`.
For photos, place optimized images in an assets folder later, or use a hosted image URL in `thumbnailUrl`.

## Cloudflare path later (free plan)
1. Keep your schema from `one-world-relief/cloudflare-d1-schema.sql` for D1.
2. Keep using the same table names so migration stays straightforward.
3. Move these backend routes into Cloudflare Workers (or Pages Functions).
4. Replace `sqlite3` calls with D1 prepared statements.
5. Keep webhook endpoints public and protect admin endpoints with `OWR_ADMIN_API_KEY`.
