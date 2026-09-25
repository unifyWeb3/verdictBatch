# Studionet evidence — VerdictBatch

Run date: 2026-09-25 UTC

This record was collected from the stable hosted Studio only. It is not a
claim about `studio-dev.genlayer.com`.

## Network and deployment

| Field | Observed value |
| --- | --- |
| Network alias | `studionet` |
| RPC | `https://studio.genlayer.com/api` |
| `eth_chainId` | `0xf22f` = `61999` |
| Deployed contract | `0xCf2E8A9b28330b6cb8ff9da72eCE6827eE20996d` |
| Deployment transaction | `0x95c588816b3b3d3016dd9aca7027f38965637eb87bc46cbc18439191ecc6f57d` |
| Deployment protocol status | `FINALIZED` |
| Deployment consensus result | `MAJORITY_AGREE` |
| Deployment leader execution | `SUCCESS` |
| Deployed source SHA-256 | `005b50903d49075ec27244268fae1cde38757262d5506e5f39c0423d45ca52cf` (matches the local contract bytes) |

The deployment receipt also contained a quorum-cancellation record for a
non-leading validator. The leader execution and protocol result were read
separately, as required; a protocol status alone was not treated as proof of
application execution.

## Fixture

```text
policy_id:  bounty-demo-v1
root:        5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2
leaf 1 hash: afc81efa7f08db2856cd3b06e94e01d7a128e2f5be0f0500c8e50bda96634c8b
proof:       ["193ddeaa57efde70d909eaccbf509a33a8b132593cc92d71d265bb4d20f873be",
              "e9a947d3683c561a778fe3bdadf1efe67aea171bec14f62ab75484d5fce873b9"]
```

The fixture has three leaves: a supported accept, an accept contradicted by
missing required tests, and an accept with conflicting/truncated evidence.

## Transactions

All listed transactions reached both `ACCEPTED` and `FINALIZED` protocol
status, had consensus result `MAJORITY_AGREE`, and had leader execution
`SUCCESS`.

| Step | Batch / action | Transaction ID |
| --- | --- | --- |
| Commit | `bounty-valid-001` | `0x75637cdce1d0b6c2abf75f86281fafcca2e4c096ea795747b2d8b591bbccbe7b` |
| Challenge | `bounty-wrong-001` / `challenge-wrong-1` | `0x72c0dbb1a5d0c0b3dc99f2268fdae401c7790c5746f5d2faa9416631d32fe762` |
| Review | `bounty-wrong-001` | `0x8d01a7ab3bf11a5d2344b19d1290938f7bdc8d044f432872b1d34c490c4fd24a` |
| Close | `bounty-valid-001` | `0xf9bbce42d013717ca61cb36797f69c63c73fe5939dd8138fc805b1cded2a1cec` |
| Commit | `bounty-ambiguous-001` | `0x404cfc247dfb1cc2f18d84620ab936954bbc56c38564efd5567ba41e17ed11f6` |
| Challenge | `bounty-ambiguous-001` / `challenge-ambig-1` | `0x00c2f981e0997518bbf301fd39fb713a4d212da5f74dd6f92f9a5bb7e6948209` |
| Review | `bounty-ambiguous-001` | `0x0d6a80af4dce68fefbe6d6e310121551402ee2a3a775c9d8b7117f240895fc05` |
| Close | `bounty-wrong-001` | `0xa4ef01f7f9ad7088a5aac61dc857db9cbc367b77968d2b3c4c6eb8016877f83c` |

The close of the wrong-leaf batch was submitted after its review window. The
first live run had a transient Studio HTTP disconnect while submitting the
ambiguous review; the same contract action ID was safely retried, and the
resulting transaction is the one recorded above.

## Application state reads

### Uncontested valid batch

`get_batch("bounty-valid-001")` returned:

```text
status:             FINALIZED_VALID
root:               5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2
operator_refund:    10
challenger_reward:  0
fraud_status:       NOT_ASSERTED
```

### Wrong leaf

`get_review("bounty-wrong-001", "challenge-wrong-1", 1)` returned:

```text
outcome:     CONTRADICTED
reason_code: MISSING_REQUIRED_ARTIFACTS
consensus:   ACCEPTED
```

The batch then reached `FINALIZED_INVALID`. Its settlement record was:

```text
operator_bond:     10
operator_refund:   7
challenger_bond:   5
challenger_refund: 5
challenger_reward: 3
fraud_status:      NOT_ASSERTED
```

The reward is an explicit internal application accounting transfer. It is not
a fraud finding and not native-token escrow.

### Ambiguous leaf

`get_review("bounty-ambiguous-001", "challenge-ambig-1", 1)` returned:

```text
outcome:     INCONCLUSIVE
reason_code: conflicting_or_truncated_evidence
consensus:   ACCEPTED
```

`get_batch("bounty-ambiguous-001")` returned `UNRESOLVED` and
`fraud_status=NOT_ASSERTED`. It was intentionally left unresolved rather than
being converted to invalid or silently closed. Its operator and challenger
bonds remain locked pending `retry_review` or `close_unresolved`.

Final bond reads also showed `operator available=17, locked=10` and
`challenger available=8, locked=5`, which is consistent with the unresolved
batch still holding its two internal bonds.

## Local and Studio checks

- `python3 -m pytest -q`: **22 passed**.
- `GENVMROOT=/tmp/opencode/genvmroot .venv/bin/genvm-lint check contracts/verdict_batch.py`: **lint and SDK validation passed**, 21 methods (12 view, 9 write).
- Studio `sim_lintContract`: **0 errors, 0 warnings, 0 info**.
- Studio `gen_getContractSchemaForCode`: schema extracted successfully.
- SHA-256/Merkle check: the contract's `SHA256("abc")` matched Python
  `hashlib.sha256`, and the contract root matched an independent test
  implementation.

## Not verified by this run

- Production native-token escrow, withdrawals, slashing, or a fraud-proof lane.
- Multiple simultaneous challenges.
- Deterministic behavior of any particular hosted LLM; the live verdicts are
  evidence of this run, not a guarantee for future validator/model sets.
- A second independent Studio deployment or the `studio-dev` preview network.
