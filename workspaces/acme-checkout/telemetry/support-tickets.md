# Customer support queue (Zendesk export, rolling). All times UTC.
# Sliceable by date; most of these cluster around customer-facing incidents.

- ZD-4471 | 2026-06-16T14:51Z | "Can't check out" | "I click pay and it just spins, then says something went wrong. Tried 3 times." | priority: urgent | service_area: checkout
- ZD-4472 | 2026-06-16T14:54Z | "Payment failing" | "Order won't go through, error 504. I have items in my cart ready to buy!" | priority: urgent | service_area: checkout
- ZD-4475 | 2026-06-16T15:02Z | "Checkout broken?" | "Is the site down? Can't complete my purchase." | priority: high | service_area: checkout
- ZD-4476 | 2026-06-16T15:08Z | "Still can't pay" | "Been trying for 20 minutes." | priority: high | service_area: checkout
- ZD-4392 | 2026-06-12T10:09Z | "Order error during sale" | "Tried to grab the promo deal and got an error." | priority: high | service_area: checkout
- ZD-4310 | 2026-06-10T21:15Z | "Login problems" | "Keeps saying my session expired when I try to do anything." | priority: normal | service_area: auth
- ZD-4288 | 2026-06-09T08:20Z | "Wrong recommendations" | "The 'recommended for you' looks off." | priority: low | service_area: recommendations

# revenue note: checkout outages map ~1:1 to lost orders (~$4.2k/min at peak) — see slos.yaml.
