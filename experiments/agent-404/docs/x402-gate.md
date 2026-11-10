# x402 integration gate: NO REAL PAYMENTS ENABLED

The experiment currently uses **free** access. Do not expose a fake `HTTP 402` without settlement validation.

Future checklist:

1. Choose testnet, stablecoin contract and licensed/acceptable payment intermediary based on current x402 V2 support.
2. Confirm facilitator `/supported` result for the chosen protocol version, payment scheme and network.
3. Store network, recipient address and all credentials as deployment secrets, never in Git history or frontend.
4. Implement price quote, V2 `PAYMENT-REQUIRED` header and verification + settlement with official maintained middleware. Make requests idempotent and don't grant access until settlement finalizes.
5. In testnet, exercise insufficient funds, invalid signature, replayed signatures, duplicate requests, wrong chain, facilitator timeout and charge-on-failure handling.
6. Verify business entity, legal disclosures, invoicing, tax treatment and payout reconciliation before any mainnet launch.
7. Only after a separate authorization, publish paid endpoint metadata to Bazaar and verify it is indexed.

Source: https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md
