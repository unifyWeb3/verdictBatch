# Studionet evidence — VerdictBatch

Run window: 2026-09-27 UTC (hosted Studio session)

This record was collected from the stable hosted Studio only. It is not a claim about `studio-dev.genlayer.com`.

## Network and deployment

| Field | Observed value |
| --- | --- |
| Network alias | `studionet` |
| RPC | `https://studio.genlayer.com/api` |
| `eth_chainId` | `0xf22f` = `61999` |
| Deployed contract | `0xEa9201204e56C09dd94fD243A22B99261C9504E9` |
| Deployment transaction | `0x479668f3346a75b752fb6e01019ec55d969b49ae42f5929b48532fc6c7f11ec9` |
| Deployment result | `MAJORITY_AGREE` |
| Deployment protocol status | `FINALIZED` |
| Deployment leader execution | `SUCCESS` |
| Deployed source SHA-256 | `ce51ae2a9baa5064814a25e0861d66d6572eb0e56b795cc79b4be304056c50d8` |

The deployment transaction and source bytes were read back from Studio. Protocol status and leader execution are recorded separately.

## Fixture

- policy: `bounty-demo-v1`, challenge window `60s`, review window `300s`
- root: `5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2`
- leaves: `3` canonical JSON objects

## Transaction evidence

| Label | Transaction | Accepted | Consensus | Finalized | Consensus | Leader execution |
| --- | --- | --- | --- | --- | --- | --- |
| `finalize_valid_final` | `0x799df2c9b137ce16b0862393f934a488ae31c14a7d6f4c786fb841b81201d6d1` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `mark_interrupted_wrong` | `0x16e3cf36b7e3b74a1d2df1ad04df500bdd6149216b8e830ea43be7b693abc138` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `fund_challenger_extra` | `0x7187b14ffaeb5c90a5b365b4bc10f191bef67d9f456a41a1621a149a8e21060c` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `challenge_ambiguous_final` | `0xb9c191dfe9a10017e838182c2ca9d71b6ca0ba6fe4b59aa2dcc67de6773bfec6` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | ERROR |
| `commit_wrong_final2` | `0xabc6cbdce916831135a45a1d24c7d8aad5e85217f115f0bb07bddfc01077ecdb` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `challenge_wrong_final2` | `0xdad69c532de3380db02078ddcc6c664a8080204a40b30c7c89da2a0d50c502bd` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `review_wrong_final2` | `0x5c8c38b7d6ec190c353ae6722b0e14b238fbf07362f8869528c609c4089a4e7b` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `review_ambiguous_final` | `0x55db86c440c4d332869dd0b8abf0d2d33448df2f12dffe9723c6d1440b41c4b5` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | ERROR |
| `finalize_wrong_final2` | `0xaba0f9d7f5a3544b2032c11916be6c9cb22301d9291aca82dc311779a6903fc3` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `finalize_old_ambiguous` | `0x04ffacc2648261422ac511564c087e94a77b751334d230d617374187dac7dcbd` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `close_old_wrong` | `0x4000091fdd9024dea68a848dc594abface3c120e058a1db9dc04e1df57600621` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `fund_operator_ambiguous2` | `0xd85eebef42a67305150c5d0f1f8419c4dc6d1fa9a62982e77d4449d83fdff946` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `commit_ambiguous_final2` | `0x60ac95d8f37243fea171a2fb5dc54d2a73b97fe4cff505a490309ef76c45aabc` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `challenge_ambiguous_final2` | `0x0b16fbcb1c880be9197ab1c3d1c217e0b90db1d465cdb616bb3451547dac2dab` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `mark_ambiguous_final2` | `0xd5007dda4a24645426f24535cba4c57184957b940821d8d88ef4a55309576714` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `fund_operator_final` | `0xeec5a6e7208728b44a2565433080b850a9a13d4f5894da84f27db249c31d45b1` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `fund_challenger_final` | `0xabd9a266254625c5a6f27bc3f463cbfdfc081f2ed01de6ee2b7880e37433f77e` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |
| `commit_valid_final` | `0x08e91c58856865e05cb2e7c6c44a26c32e8f5d641fe1da3849dcf81b55cdcdfc` | ACCEPTED | MAJORITY_AGREE | FINALIZED | MAJORITY_AGREE | SUCCESS |

The `review_ambiguous_final` transaction reached protocol `FINALIZED`/`MAJORITY_AGREE` but its leader execution was `ERROR`; the application review was not written. This is why protocol status is not treated as execution success. The fresh ambiguous case below is explicitly resolved to `UNRESOLVED` after its review window.

## Application state reads

### Valid batch

```json
{"active_challenge_id":"","batch_id":"bounty-valid-final","challenge_deadline":1790489289,"challenger_bond":"0","content_digest":"a566afca8a13d742d515bf5c0451e3efeef0548f49ce0405744a469699349639","created_at":1790489229,"fraud_status":"NOT_ASSERTED","leaf_count":3,"operator":"0x219fc0413600da962b5ddbcbf4ae3550fd7ed398","operator_bond":"10","policy_hash":"81269cfd069f2e76630151d3968ba1c50e09510066812d5ce2a2af74be4b153c","policy_id":"bounty-demo-v1","review_deadline":1790489289,"root":"5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2","settled":true,"settled_at":1790534759,"settlement":{"challenger_bond":"0","challenger_refund":"0","challenger_reward":"0","operator_bond":"10","operator_refund":"10"},"status":"FINALIZED_VALID","tree_leaf_count":4,"unresolved_deadline":1790489289,"version":2}
```

### Wrong-leaf review

```json
{"batch_id":"bounty-wrong-final2","challenge_id":"challenge-wrong-final2","evidence_digest":"f283a2fae19225f6d72a8fc6f710ed42162e49051463a48c42d960c4e55a6899","input_digest":"06c0e492e1c6fbe02fe895c33a9d7261cf775e55226b3196d5847611ad1ae5ac","normalization":"SCHEMA_VALIDATED","outcome":"CONTRADICTED","reason_code":"MISSING_REQUIRED_ARTIFACT","round":1}
```

### Wrong-leaf settlement

```json
{"active_challenge_id":"challenge-wrong-final2","batch_id":"bounty-wrong-final2","challenge_deadline":1790535037,"challenger_bond":"5","content_digest":"a566afca8a13d742d515bf5c0451e3efeef0548f49ce0405744a469699349639","created_at":1790534977,"fraud_status":"NOT_ASSERTED","leaf_count":3,"operator":"0x219fc0413600da962b5ddbcbf4ae3550fd7ed398","operator_bond":"10","policy_hash":"81269cfd069f2e76630151d3968ba1c50e09510066812d5ce2a2af74be4b153c","policy_id":"bounty-demo-v1","review_deadline":1790535317,"root":"5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2","settled":true,"settled_at":1790535357,"settlement":{"challenger_bond":"5","challenger_refund":"5","challenger_reward":"3","operator_bond":"10","operator_refund":"7"},"status":"FINALIZED_INVALID","tree_leaf_count":4,"unresolved_deadline":1790535317,"version":4}
```

### Fresh ambiguous batch

```json
{"active_challenge_id":"challenge-ambiguous-final2","batch_id":"bounty-ambiguous-final2","challenge_deadline":1790535717,"challenger_bond":"5","content_digest":"a566afca8a13d742d515bf5c0451e3efeef0548f49ce0405744a469699349639","created_at":1790535657,"fraud_status":"NOT_ASSERTED","leaf_count":3,"operator":"0x219fc0413600da962b5ddbcbf4ae3550fd7ed398","operator_bond":"10","policy_hash":"81269cfd069f2e76630151d3968ba1c50e09510066812d5ce2a2af74be4b153c","policy_id":"bounty-demo-v1","review_deadline":1790535999,"root":"5f06c3a445a53392f9550a33141cc879204ae74159cf59a74206feba5b690fd2","settled":false,"status":"UNRESOLVED","tree_leaf_count":4,"unresolved_deadline":1790536326,"version":3}
```

### Fresh ambiguous review record

```json
{"batch_id":"bounty-ambiguous-final2","challenge_id":"challenge-ambiguous-final2","evidence_digest":"03f4f5e8faa35e9913f12f6e39aa26919c9d366672d6d34f6fdd21ed5f67c997","input_digest":"babb9ca56488485bfc9240fd0c3023f36f3703a4a91d10c04b70d0da20302545","outcome":"INCONCLUSIVE","reason_code":"NO_CONSENSUS_OR_EXPIRED","resolution":"DEADLINE","round":1}
```

### Downstream actionability (valid)

```json
true
```

### Downstream actionability (invalid)

```json
false
```

### Downstream actionability (unresolved)

```json
false
```

### Operator bond ledger

```json
{"available":"27","deposited":"40","locked":"10","refunded":"37","reward_received":"0"}
```

### Challenger bond ledger

```json
{"available":"13","deposited":"15","locked":"5","refunded":"10","reward_received":"3"}
```

### Ambiguous fraud status

```json
NOT_ASSERTED: application verdicts are not fraud findings
```

## Local and Studio checks

- `python3 -m pytest -q`: **29 passed**.
- `GENVMROOT=/tmp/opencode/genvmroot .venv/bin/genvm-lint check contracts/verdict_batch.py`: **lint and SDK validation passed**, 22 methods (13 view, 9 write).
- Studio `sim_lintContract`: **0 findings** (0 errors, 0 warnings, 0 info).
- Studio `gen_getContractSchemaForCode`: **22 methods** (13 view, 9 write).
- SHA-256/Merkle tests compare the contract digest of `b"abc"` with Python `hashlib.sha256` and compare the root with an independent implementation.

## Known limitations of this run

- The first attempted final flow was interrupted by a server restart after a valid commit; that interrupted batch is recorded as a known operational artifact, not counted as a successful challenge review.
- A hosted LLM review can fail or disagree; the contract leaves the application state unchanged and the deadline path records `UNRESOLVED`.
- Bonds are internal application accounting, not native-token escrow.
- One active challenge per batch, bounded review rounds, and no production withdrawal/slashing/fraud-proof lane are implemented in v1.
