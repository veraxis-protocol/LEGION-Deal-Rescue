# Security and privacy

**No secrets in this repository.**
- The NVIDIA NIM key is read from a local file whose path you pass at run time.
- PayPal REST credentials stay sealed with Windows DPAPI on the operator's host.
- The owner's control key is passphrase-protected and never leaves its key store.

**Least authority.**
- The app server is read-only and binds to `127.0.0.1`. It has no write endpoints, makes no model calls and makes no PayPal calls.
- The payment adapter has no force flag, no mock live mode and no fallback approval.
- A capture requires all of the following:
  - a current signed authorization;
  - a one-time permit;
  - a held reservation;
  - PayPal's own report that the buyer approved.

**Isolation between parties.**
- Each of the seven parties runs in its own process with its own key and private terms.
- The Judge checks that no party's private value appears outside that party. An earlier attempt failed exactly this check and is kept as evidence.

**Public evidence is redacted.**
- `demo_evidence` excludes each party's private configuration and journals, local endpoints, the Sandbox merchant ID and payer identities.

**Reporting.** Please use a private security advisory on this repository.
