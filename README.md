# VerdictBatch

VerdictBatch is an evidence-gated batch adjudication primitive for GenLayer
Intelligent Contracts. It is deliberately small: one operator commits a batch,
a challenger requests independent review of one committed leaf, and validators
review that leaf under a declared policy.

The contract is policy-driven and domain-neutral. The files under `examples/`
are only a bounty/deliverable-review fixture.

## Repository layout

- `contracts/verdict_batch.py` — the deployable Intelligent Contract.
- `tests/` — direct tests with a local GenLayer stand-in and fixed evidence
  fixtures. No provider or network access is required.
- `scripts/prepare_demo.py` — independent SHA-256/Merkle preparation helper.
- `examples/` — policy JSON and three-leaf bounty/deliverable fixture.
- `evidence/` — read-only live Studionet evidence record.
- `requirements-dev.txt` — pinned test and contract-validation dependencies.
- `.env.example` — placeholder configuration only.

## Semantics

Application states are independent of the GenLayer protocol transaction state:

| Application state | Meaning |
| --- | --- |
| `COMMITTED` | Root and leaves are committed; challenge window is open. |
| `CHALLENGED` | One active leaf challenge is recorded and its internal ledger units are locked. |
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
validator disagreement is rejected by the validator and does not write a
review or silently become a successful challenge. A schema-valid
`INCONCLUSIVE` response is recorded as normalized evidence and remains
`UNRESOLVED`. The challenger reason is stored and digest-bound, but is not sent
to the model as instructions; only the declared policy and committed leaf
evidence drive the review. `get_review`'s `normalization=SCHEMA_VALIDATED` is a
contract-side schema marker; it is not a GenLayer protocol status.

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

## Exact v1 boundaries

These boundaries are intentional and are not a promise of a production dispute
or bond system:

- A challenge is a permissionless request for independent review of one
  committed leaf. It is not a counter-evidence submission.
- The challenger's `reason` is audit metadata and is digest-bound. It is not
  counter-evidence and is not sent to the model as evidence.
- `fund_bond` credits internal application units only. It is not payable, does
  not custody funds, and does not transfer native GEN.
- Refunds and `reward_on_invalidation` are internal accounting entries. They
  are not slashing, escrow, or an enforceable economic transfer.
- Only `FINALIZED_VALID` is downstream-actionable. `FINALIZED_INVALID`,
  `UNRESOLVED`, `CHALLENGED`, and all other states are not actionable.
- v1 allows one active challenge per batch and a bounded number of review
  rounds.
- Native GEN settlement, external evidence sources, and real economic security
  are future work outside this contribution.

## Requirements

- Python 3.12+ for the direct tests and preparation script.
- GenLayer Studio at <https://studio.genlayer.com/> for the live flow.
- Use the stable hosted network only:

```text
alias:    studionet
RPC:      https://studio.genlayer.com/api
chain ID: 61999
```

Do not use `studio-dev.genlayer.com` (chain ID `61997`) for this contribution.
It is a separate preview network.

Install the pinned development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Direct verification

From the repository root:

```bash
python3 -m pytest -q
.venv/bin/genvm-lint lint contracts/verdict_batch.py
GENVMROOT=/path/to/extracted/genvm-v0.2.16 \
  .venv/bin/genvm-lint check contracts/verdict_batch.py
```

The successful SDK validation used an already extracted GenVM **v0.2.16**
runner. `GENVMROOT` is configurable; the successful command shape is shown
above. The plain linter download path was not verified in this environment and
must not be treated as equivalent without a working runner/artifact source.

The direct suite covers empty/malformed batches, duplicate leaf IDs, invalid
Merkle proofs, owner authorization, self-challenge, duplicate challenges,
expired windows, insufficient operator and challenger bonds, all three review
outcomes, malformed LLM JSON, schema-shaped digest-mismatched output, provider
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
   `challenge_window_seconds` (60 seconds in the fixture) has elapsed, then
   call `finalize_batch("finalize-bounty-001", "bounty-001")`. Read
   `get_batch` and `get_batch_status`; the expected application state is
   `FINALIZED_VALID`, with the operator bond returned. This is an application
   transition, not a claim that the GenLayer protocol transaction is finalized
   until its own status is checked.
6. For a second batch, repeat steps 3–4 with a new batch ID. From a different
   account, fund the policy minimum bond, then call `challenge_leaf` using the
   proof for leaf `1`. The expected state is `CHALLENGED`; an invalid or
   altered proof must fail without locking the challenger bond. Permissionless
   means any funded address may challenge; the operator cannot challenge its
   own batch.
7. Call `review_challenge` from any account. The contract supplies the
   validator/LLM the policy, canonical leaf evidence, and digest-bound JSON
   schema. Wait for the GenLayer transaction's **execution result** as well as
   its protocol status. Read `get_review`, `get_batch_status`, and
   `get_fraud_status`. A `CONTRADICTED` result should become `INVALIDATED`; a
   `SUPPORTED` result should become `UPHELD`; a schema-valid `INCONCLUSIVE`
   result becomes `UNRESOLVED`. A malformed or non-convergent response must not
   write a review or become `FINALIZED_INVALID`.
8. For an `INVALIDATED` or `UPHELD` batch, wait until the policy's
   `review_window_seconds` has elapsed, then call `finalize_batch`. Read the
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
is_downstream_actionable(batch_id)
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

The live run is recorded in
[`evidence/studionet-2026-09-27.md`](evidence/studionet-2026-09-27.md). The
observed final deployment was:

```text
network alias:       studionet
RPC:                 https://studio.genlayer.com/api
chain ID:            61999 (eth_chainId 0xf22f)
contract address:    0xEa9201204e56C09dd94fD243A22B99261C9504E9
deploy transaction:  0x479668f3346a75b752fb6e01019ec55d969b49ae42f5929b48532fc6c7f11ec9
source SHA-256:      ce51ae2a9baa5064814a25e0861d66d6572eb0e56b795cc79b4be304056c50d8
valid commit:        0x08e91c58856865e05cb2e7c6c44a26c32e8f5d641fe1da3849dcf81b55cdcdfc
valid close:         0x799df2c9b137ce16b0862393f934a488ae31c14a7d6f4c786fb841b81201d6d1
wrong commit:        0xabc6cbdce916831135a45a1d24c7d8aad5e85217f115f0bb07bddfc01077ecdb
wrong challenge:     0xdad69c532de3380db02078ddcc6c664a8080204a40b30c7c89da2a0d50c502bd
wrong review:        0x5c8c38b7d6ec190c353ae6722b0e14b238fbf07362f8869528c609c4089a4e7b
wrong close:         0xaba0f9d7f5a3544b2032c11916be6c9cb22301d9291aca82dc311779a6903fc3
ambiguous commit:    0x60ac95d8f37243fea171a2fb5dc54d2a73b97fe4cff505a490309ef76c45aabc
ambiguous challenge: 0x0b16fbcb1c880be9197ab1c3d1c217e0b90db1d465cdb616bb3451547dac2dab
ambiguous mark:      0xd5007dda4a24645426f24535cba4c57184957b940821d8d88ef4a55309576714
failed LLM review:   0x55db86c440c4d332869dd0b8abf0d2d33448df2f12dffe9723c6d1440b41c4b5
```

The run read back `FINALIZED_VALID` for the uncontested batch,
`FINALIZED_INVALID` with a reward of `3` for the contradicted leaf, and
`UNRESOLVED` for the ambiguous leaf. The failed LLM review transaction reached
protocol `FINALIZED`/`MAJORITY_AGREE` but its leader execution was `ERROR`; no
application review was written. The evidence file records protocol status,
consensus result, and leader execution result separately.

This is a live Studionet demonstration, not production escrow. The ambiguous
batch was intentionally left `UNRESOLVED`; its locked internal bonds are
released only by a later `retry_review`/`close_unresolved` path. An earlier
run was interrupted by a server restart; its cleanup and the final run are
both recorded in the evidence file.
