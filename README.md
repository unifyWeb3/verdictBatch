# VerdictBatch

VerdictBatch is an evidence-gated, leaf-disputable batch adjudication
primitive for GenLayer Intelligent Contracts. It is deliberately small: one
operator commits a batch, a challenger disputes one leaf, and validators review
that leaf under a declared policy.

The contract is policy-driven and domain-neutral. The files under `examples/`
are only a bounty/deliverable-review fixture.

## Repository layout

- `contracts/verdict_batch.py` — the deployable Intelligent Contract.
- `tests/` — direct tests with a local GenLayer stand-in and fixed evidence
  fixtures. No provider or network access is required.
- `scripts/prepare_demo.py` — independent SHA-256/Merkle preparation helper.
- `examples/` — policy JSON and three-leaf bounty/deliverable fixture.
- `.env.example` — placeholder configuration only.

## Semantics

Application states are independent of the GenLayer protocol transaction state:

| Application state | Meaning |
| --- | --- |
| `COMMITTED` | Root and leaves are committed; challenge window is open. |
| `CHALLENGED` | One active leaf challenge is escrowed internally. |
| `UPHELD` | Review outcome was `SUPPORTED`; the original decision survives. |
| `INVALIDATED` | Review outcome was `CONTRADICTED`; the batch is rejected. |
| `UNRESOLVED` | Review was `INCONCLUSIVE`, or no consensus was recorded. |
| `FINALIZED_VALID` | Valid application outcome; internal bonds settled. |
| `FINALIZED_INVALID` | Invalid application outcome; internal bonds settled. |
| `CANCELED` | Undisputed batch canceled or unresolved dispute closed. |

Review outcomes are statements about the **original committed decision**:

- `SUPPORTED` — the original decision survives under the policy.
- `CONTRADICTED` — the original decision is invalid under the policy.
- `INCONCLUSIVE` — evidence is missing, conflicting, ambiguous, or
  insufficient. This never becomes fraud and never becomes a successful
  challenge by default.

The v1 model is intentionally neutral: a validator/LLM disagreement is not
called fraud, does not set a fraud flag, and does not by itself confiscate a
bond. Fraud/malice language is reserved for deterministic proofs such as a
forged commitment, an invalid inclusion proof, or an authorization violation.
The v1 contract rejects those proofs instead of creating a fraud state.

LLM output is constrained to a small JSON object. Validators independently
repeat the review and compare the normalized `outcome` and digests, not
free-form reasoning. Malformed output, missing evidence, a provider failure, or
validator disagreement is not silently converted into a successful challenge.

### Canonical leaves and Merkle proofs

A leaf is a JSON object with non-empty `leaf_id`, `decision`, and `evidence`
fields. The contract canonicalizes the object with sorted keys and compact
separators, then computes a real SHA-256 digest. The Merkle tree pads to a
power of two by repeating the last leaf hash; every internal node is
`SHA256(left_bytes || right_bytes)`. Proofs use the usual sibling-index rule.
The contract recomputes the root and rejects an incorrect `claimed_root` or an
invalid inclusion proof before any bond is locked.

### Internal bond accounting

`fund_bond` credits an internal ledger and is owner-only. Commit and challenge
lock the configured minimum bonds. Final settlement returns the operator and
challenger balances. For a contradicted decision, the policy's explicit
`reward_on_invalidation` amount is transferred from the operator's locked bond
to the challenger's available balance.

This is **not production escrow** and no native token transfer is performed in
v1. The ledger is an application-level accounting primitive so the flow can be
demonstrated on Studio without claiming custody of funds.

## Requirements

- Python 3.12+ for the direct tests and preparation script.
- `genvm-linter` for contract validation:

```bash
python3 -m venv .venv
.venv/bin/pip install genvm-linter
```

- GenLayer Studio at <https://studio.genlayer.com/> for the live flow.
- Use the stable hosted network only:

```text
alias:    studionet
RPC:      https://studio.genlayer.com/api
chain ID: 61999
```

Do not use `studio-dev.genlayer.com` (chain ID `61997`) for this contribution.
It is a separate preview network.

## Direct verification

From the repository root:

```bash
python3 -m pytest -q
.venv/bin/genvm-lint lint contracts/verdict_batch.py
GENVM_VERSION=genlayerlabs-genvm-v0.2.16 .venv/bin/genvm-lint check contracts/verdict_batch.py
```

The direct suite covers empty/malformed batches, duplicate leaf IDs, invalid
Merkle proofs, owner authorization, self-challenge, duplicate challenges,
expired windows, all three review outcomes, malformed LLM JSON, provider
failure, conflicting validator verdicts, settlement, refunds/rewards, and
idempotency/state guards. The LLM is replaced by a fixed local response
function; this proves contract logic, not live model behavior.

The SHA-256 check is explicit: the suite compares the contract digest of
`b"abc"` with Python's `hashlib.sha256(b"abc")`, and compares the Merkle root
with an independent implementation.

## Prepare the Studio inputs

Generate the exact `leaves_json`, root, leaf hash, and proof for the fixture:

```bash
python3 scripts/prepare_demo.py examples/bounty_batch.json --index 1
```

Use the printed `leaves_json` and `root` in `commit_batch`. Use the printed
`leaf_hash` and `proof` for leaf index `1`. The index is zero-based.

## Studio reproduction

1. Open <https://studio.genlayer.com/> and select the stable hosted network.
   Confirm the RPC is `https://studio.genlayer.com/api` and chain ID is
   `61999`. Record the account addresses used for operator, challenger, and
   reviewer. Do not mix in a `studio-dev` account or endpoint.
2. Load `contracts/verdict_batch.py` into the Studio editor. Deploy with:
   - `policy_id`: `bounty-demo-v1`
   - `policy_json`: the compact contents of `examples/demo_policy.json`
3. From the operator account, call `fund_bond` with a fresh `action_id`, the
   operator address, and `10`. Confirm `get_bond(operator)` shows
   `available=10, locked=0`.
4. Call `commit_batch` with:
   - `action_id`: `commit-bounty-001`
   - `batch_id`: `bounty-001`
   - `leaves_json` and `claimed_root`: output of `prepare_demo.py`
   - `bond_amount`: `10`

   Read `get_batch("bounty-001")` and `get_leaf(...)`; the state must be
   `COMMITTED` and the recomputed root must match.
5. To demonstrate an uncontested valid close, wait until the policy's
   `challenge_window_seconds` (120 seconds in the fixture) has elapsed, then
   call `finalize_batch("finalize-bounty-001", "bounty-001")`. Read
   `get_batch` and `get_batch_status`; the expected application state is
   `FINALIZED_VALID`, with the operator bond returned. This is an application
   transition, not a claim that the GenLayer protocol transaction is finalized
   until its own status is checked.
6. For a second batch, repeat steps 3–4 with a new batch ID. From a different
   account, fund `5`, then call `challenge_leaf` using the proof for leaf `1`.
   The expected state is `CHALLENGED`; an invalid or altered proof must fail
   without locking the challenger bond.
7. Call `review_challenge` from any account. The contract supplies the
   validator/LLM the policy, canonical leaf, evidence, and digest-bound JSON
   schema. Wait for the GenLayer transaction's **execution result** as well as
   its protocol status. Read `get_review`, `get_batch_status`, and
   `get_fraud_status`. A `CONTRADICTED` result should become `INVALIDATED`; a
   `SUPPORTED` result should become `UPHELD`; malformed or non-convergent
   output must not become `FINALIZED_INVALID`.
8. For an `INVALIDATED` or `UPHELD` batch, wait for the review window if the
   status is still `CHALLENGED`, then call `finalize_batch`. Read the
   `settlement` object and both `get_bond` records. An invalidated batch shows
   `operator_refund`, `challenger_refund`, and `challenger_reward`; the
   reward is internal accounting, not a fraud penalty.
9. To demonstrate an ambiguous case, use `deliverable-003` from the fixture.
   Its evidence deliberately contains conflicting reviewer notes and a
   truncated rubric. Call `review_challenge`; if the accepted normalized
   outcome is `INCONCLUSIVE`, the batch must be `UNRESOLVED`, not invalidated
   and not fraudulent. It can be retried with `retry_review` before the retry
   window ends, or closed with `close_unresolved` after the window/round
   limit. Read the resulting state and both bond ledgers.
10. For every write, capture the Studio transaction ID, protocol status, and
    execution result separately. Also capture the `get_batch` response. A
    transaction reported as `ACCEPTED` or `FINALIZED` by the protocol does not
    by itself prove that the contract method returned successfully.

## Method reference

Views:

```text
get_policy()
get_policy_hash()
get_batch(batch_id)
get_batch_status(batch_id)
get_leaf(batch_id, leaf_index)
get_challenge(batch_id, challenge_id)
get_review(batch_id, challenge_id, review_round)
get_bond(account)
get_action(action_id)
get_fraud_status(batch_id)
compute_merkle_root(leaves_json)
verify_merkle_proof(leaf_hash, proof_json, root, leaf_index, tree_leaf_count)
```

Writes:

```text
fund_bond(action_id, account, amount)
commit_batch(action_id, batch_id, leaves_json, claimed_root, bond_amount)
challenge_leaf(action_id, batch_id, challenge_id, leaf_index, leaf_hash,
               proof_json, reason, bond_amount)
review_challenge(action_id, batch_id, challenge_id)
mark_unresolved(action_id, batch_id, challenge_id)
retry_review(action_id, batch_id, challenge_id)
finalize_batch(action_id, batch_id)
cancel_batch(action_id, batch_id)
close_unresolved(action_id, batch_id)
```

`review_challenge` never accepts a caller-supplied outcome. `action_id`
replays with identical arguments are idempotent; reuse with different
arguments is rejected.

## Known limitations

- v1 allows one active challenge per batch and a bounded number of review
  rounds. Multiple simultaneous challenges are not implemented.
- Bonds are internal ledger entries, not native-token escrow. There is no
  production withdrawal, slashing, or fraud-proof lane yet.
- The review window and retry/close policy are application timers; they do not
  replace GenLayer protocol finality or appeal windows.
- Live LLM outcomes depend on the validators configured in Studio. The local
  fixtures test normalization and transitions, not any particular model's
  judgment.
- The contract accepts a bounded JSON string rather than an unbounded web page
  or arbitrary binary evidence. Evidence size and policy limits are explicit.
- No dashboard, external integration, or automated appeal agent is included.

## Deployment and evidence record

The live deployment record must be filled only from Studio responses; no
placeholder address or transaction ID is evidence. Record:

```text
network alias:       studionet
chain ID:            61999
contract address:    PENDING_LIVE_DEPLOYMENT
deploy transaction:  PENDING_LIVE_DEPLOYMENT
commit transaction:  PENDING_LIVE_DEMO
challenge transaction: PENDING_LIVE_DEMO
review transaction:  PENDING_LIVE_DEMO
close transaction:   PENDING_LIVE_DEMO
protocol statuses:   PENDING_LIVE_DEMO
execution results:   PENDING_LIVE_DEMO
```

Do not mark the live flow complete until the address, transaction IDs,
protocol status, and execution result have all been read back from Studio.
