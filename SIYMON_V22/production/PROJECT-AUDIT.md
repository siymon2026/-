# SIYMON v19 — source audit before production

Read from the attached `siymon_v19_driver_docs_toggle.zip` (app2-arena-91e90e1a-app2)
plus the supplied interface screenshots. Every scene is checked against this file.

## Real order lifecycle (`lib/order-state.js`)

```
new → admin_accepted → restaurant_ready → accepted → picked_up → on_the_way → delivered → done
                                                    (canceled exits anywhere)
```

- The **store** moves an order to `restaurant_ready` (= released to drivers).
- The **driver** then moves it `restaurant_ready → accepted → picked_up → on_the_way → delivered → done`.
- A driver may never skip or rewind a step; terminal orders cannot be re-completed.

## Verification (`lib/verify-codes.js`)

- Two independent 6-digit stages: **pickup** (shown to the store) and **delivery** (shown to the customer).
- The driver **never** receives either code — the driver types what the other party shows.
- 5 attempts, 10-minute lock, 24 h expiry, one-time use.

## Payments actually available (`lib/payment-methods.js`)

| Method | Reality |
|---|---|
| Cash on delivery (COD) | enabled, order payment only |
| Card terminal (TPE) **at delivery** | enabled, order payment only |
| CIH / Crédit Agricole / Cash Plus / Wafacash / Attijariwafa / Barid / manual bank transfer | **manual transfer**, needs a human supervisor to verify |
| Stripe | **NOT integrated** — permanently unavailable ("غير متوفر حاليا") |

→ Videos show only: banknote (COD), card terminal at hand-over (TPE), and a bank-app
transfer that stays **pending** until verified. Never an instant card success.

## Dispatch (`lib/dispatch-service.js`, `lib/hexcell.js`)

- Hexagonal grid, **real 500 m cells**, pointy-top, anchored on Berrechid 33.265 / -7.59.
- Dispatch rings default **3 rings** of 500 m cells (~1.3 km) around the pickup.
- Modes: `pull` (default) and `offers`; offers expire (default TTL 10–120 s).
- Driver states: `offline` → `online` → `offer_pending` → `assigned` → `delivering`.

## Money (`lib/driver-earnings.js`, `lib/delivery-pricing.js`, `lib/wallet-*`)

- Driver earning = order `deliveryFee`, or `base + roadKm × perKm` (snapshot at order creation).
- Customer wallet has a real ledger; top-ups use the same transfer methods.
- Currency **MAD (د.م.)**; prices are small 2-decimal numbers.

## Brand (`public/brand.css` — single source of truth)

| Token | Value |
|---|---|
| background | `#0F0F0F` |
| surface | `#202020` |
| primary green | `#5DD62C` |
| primary dark | `#337418` |
| text | `#F8F8F8` |
| muted | `#A8A8A8` |

Logo = green rounded-square app icon with the white/green "S" swoosh
(`public/icons/icon-192.png`). No new logo is invented.

## Interface vocabulary reused (shapes only, no words on screen)

- Customer: dark home, store cards with cover image, category chips, cart badge,
  green pill CTA, bottom nav (home / cart / store / bell / profile).
- Store panel: tabs Orders | Products, product grid, availability switch, green CTA.
- Driver app: online toggle, today/week/month earnings, offer card with
  pickup→dropoff and distance, 6-digit code pad, live route map, bottom nav.
- Wallet: balance hero, top-up button, ledger rows.
