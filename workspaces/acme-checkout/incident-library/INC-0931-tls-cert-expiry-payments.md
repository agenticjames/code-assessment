---
id: INC-0931
title: payment-gateway outage from an expired TLS certificate
date: 2025-12-19
severity: SEV1
services: [payment-gateway, checkout]
duration: 34m
tags: [tls, certs, payment-gateway, expiry, external]
---

## Summary
Payments failed for ~34 minutes because the **TLS certificate** used to connect to the
**payment-gateway** had **expired**. Every attempt to establish a secure connection to the processor
was rejected at the handshake, so checkout could not complete card payments. The failure was a
**certificate lifecycle** problem, not capacity, code, or infrastructure load.

## Timeline (UTC)
- 11:02  Checkout payment attempts begin failing; logs show TLS handshake errors to payment-gateway.
- 11:06  Confirmed: the client certificate for the payment-gateway integration **expired** at 11:00.
- 11:14  Card payments are fully failing; checkout cannot place paid orders.
- 11:22  Rotated in a renewed certificate; handshakes succeed again.
- 11:36  Payments recover; backlog of retried orders clears.

## Root cause
The TLS certificate for the payment-gateway connection reached its **expiry** and was not rotated in
time. Once expired, the handshake failed and no payment traffic could flow. This is an
**expired-cert** failure — distinct from the processor being slow/flaky and unrelated to anything in
the internal stack (Redis, rate-limiter, auth, DB).

## Resolution / fix
- **Immediate:** rotated to a valid certificate and redeployed the payment-gateway client config.
- **Follow-up:** automated certificate renewal + an expiry alert that pages **well before**
  certificates lapse.

## Lessons learned
- TLS handshake errors to an external dependency point straight at **certificates** (expiry, trust
  chain), not at load or capacity. Check cert validity dates first.
- Certificate expiry is a **time-bomb**: it fires regardless of traffic. Track expiries and renew
  ahead of time rather than reacting to the outage.
