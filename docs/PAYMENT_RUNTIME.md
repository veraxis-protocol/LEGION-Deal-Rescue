# Which code made the five PayPal captures

| Payments | Code | Command |
|---|---|---|
| Customer A | LEGION-Commerce `9e1f3d6591b679d6ffb619433a4d25f1235664af` | `python -m commerce_demo.lmf007 run` |
| Customers B–E | LEGION-Commerce `0bb385f99915a429d0c03fa8f91a13de4e8a7636` | `python -m commerce_demo.lmf007 run` |

**The two commits.** Both are on branch `claude/wo-004-final-release`. They differ in a single file,
`commerce_demo/readback.py`: the comparison fix described in [PAYPAL_STATUS.md](../PAYPAL_STATUS.md). That fix was applied after
Customer A's capture and before Customer A's passing readback. The order, approval and capture path is identical in both.

**Published in this repository.** `paypal_adapter/commerce_adapter/` is **byte-identical** to `commerce_adapter/` at both commits. It
is also the exact source bound by the pending independent acceptance request (A03 v5). The SHA-256 of every file is in
[PAYMENT_RUNTIME.json](PAYMENT_RUNTIME.json):

| File | SHA-256 |
|---|---|
| `__init__.py` | `f4b5a6451c984786b82936c80f1a08bfe977219a1d9efd5674b089b166abb536` |
| `__main__.py` | `8e72c9b3391fe6d79a9658ee42f6e1ebbcc1b6f10ea0b97137e568cb4a25dec5` |
| `approval.py` | `03fd03bde61168bb9b0f6526824a18290ec5a57b53df27d8cb798fa3f0d10937` |
| `contracts.py` | `ed44966830509ee97a28765eefd23a0f68f49be7b82129ad6dc49e8056c6fbac` |
| `gateway.py` | `164b414ccf782e73819065fed0f1fbe067e7925f6bbfeb79fcd633a19950f9ea` |
| `paypal.py` | `9e0f582ce01e261fca18ab4b5273755f122ef33c52cf4754f5d6083d6c7dba4c` |
| `readback.py` | `66c38645f5aadaa7447800b14d3245e8a4657d63ec0944643460ef0a09c5a5e7` |

**Used in place, not copied.** These are referenced by commit and file hash (all hashes are in the JSON):

| Code | Location | License |
|---|---|---|
| Payment orchestration: `commerce_demo` (per-payer authorization, run loop, independent readback) | LEGION-Commerce | No license file in that repository |
| Admission bridge: `commerce_bridge` | LEGION-Commerce | No license file in that repository |
| Owner key custody: `commerce_authority` | LEGION-Commerce | No license file in that repository |
| Admission runtime source | LEGION Core `d083c44` | Public |
| Admission runtime source | ZTL `e1141c6` | Public |
| Admission runtime source | ztl-swarm `7d2a826` | Public |
| Qualified LEGION runtime (decider binary SHA-256 `99cda684…ade73a`) | `d9d38cd` | **Not published** |

**How to check.**
1. Hash `paypal_adapter/commerce_adapter/*.py` in this repository and compare the results with the table above.
2. Clone LEGION-Commerce at `0bb385f`, hash the same files, and compare again.
3. Compare the events journals in `demo_evidence/paypal_runs/*/END_TO_END_EVENTS.jsonl`: each payment's permit and admission decision appear there, followed by exactly one order POST and one capture POST.
