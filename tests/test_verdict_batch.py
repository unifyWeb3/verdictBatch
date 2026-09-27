import hashlib
import json

import pytest

from genlayer_stub import ConsensusFailure, UserError, digest_from_prompt, make_leaves


OPERATOR = "0x" + "11" * 20
CHALLENGER = "0x" + "22" * 20
OTHER = "0x" + "33" * 20


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pair(left: str, right: str) -> str:
    return _sha256(bytes.fromhex(left) + bytes.fromhex(right))


def _root(leaves):
    hashes = [_sha256(json.dumps(leaf, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) for leaf in leaves]
    size = 1
    while size < len(hashes):
        size *= 2
    hashes += [hashes[-1]] * (size - len(hashes))
    while len(hashes) > 1:
        hashes = [_pair(hashes[i], hashes[i + 1]) for i in range(0, len(hashes), 2)]
    return hashes[0]


def _proof(leaves, index):
    hashes = [_sha256(json.dumps(leaf, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) for leaf in leaves]
    size = 1
    while size < len(hashes):
        size *= 2
    hashes += [hashes[-1]] * (size - len(hashes))
    result = []
    while len(hashes) > 1:
        result.append(hashes[index ^ 1])
        hashes = [_pair(hashes[i], hashes[i + 1]) for i in range(0, len(hashes), 2)]
        index //= 2
    return result


def _sender(env, address):
    env["gl"].message.sender_address = address


def _fund(env, address, amount, action):
    _sender(env, address)
    env["contract"].fund_bond(action, address, amount)


def _commit(env, batch_id="batch-1", action="commit-1", bond=10, leaves=None):
    leaves = leaves or make_leaves()
    _sender(env, OPERATOR)
    return env["contract"].commit_batch(
        action,
        batch_id,
        json.dumps(leaves, separators=(",", ":")),
        _root(leaves),
        bond,
    )


def _challenge(env, batch_id="batch-1", challenge_id="challenge-1", index=1, action="challenge-action-1", bond=5, reason="The decision conflicts with the rubric.", proof=None, leaves=None):
    leaves = leaves or make_leaves()
    proof = proof if proof is not None else _proof(leaves, index)
    _sender(env, CHALLENGER)
    return env["contract"].challenge_leaf(
        action,
        batch_id,
        challenge_id,
        index,
        _sha256(json.dumps(leaves[index], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()),
        json.dumps(proof, separators=(",", ":")),
        reason,
        bond,
    )


def _setup_challenged(env, batch_id="batch-1", challenge_id="challenge-1", index=1):
    _fund(env, OPERATOR, 10, "fund-operator-" + batch_id)
    _fund(env, CHALLENGER, 5, "fund-challenger-" + batch_id)
    _commit(env, batch_id=batch_id, action="commit-" + batch_id)
    _challenge(env, batch_id=batch_id, challenge_id=challenge_id, index=index, action="challenge-" + batch_id)


def _set_prompt(env, outcomes):
    """Set a sequence of normalized LLM answers for leader and validator calls."""
    values = list(outcomes)

    def handler(prompt, **kwargs):
        input_digest, evidence_digest = digest_from_prompt(prompt)
        outcome = values.pop(0) if values else values_default
        if isinstance(outcome, str) and outcome == "RAISE":
            raise RuntimeError("simulated provider failure")
        if isinstance(outcome, str) and outcome == "MALFORMED":
            return "not json"
        return {
            "outcome": outcome,
            "reason_code": "FIXTURE",
            "input_digest": input_digest,
            "evidence_digest": evidence_digest,
        }

    values_default = outcomes[-1]
    env["gl"].prompt_handler = handler


def _review(env, batch_id="batch-1", challenge_id="challenge-1", action="review-action"):
    _sender(env, OTHER)
    return env["contract"].review_challenge(action, batch_id, challenge_id)


def _status(env, batch_id="batch-1"):
    return env["contract"].get_batch_status(batch_id)


def test_sha256_merkle_uses_real_sha256(contract_env):
    module = contract_env["module"]
    assert module._sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()
    leaves = make_leaves()
    assert _root(leaves) == module._merkle_root_from_hashes(module._leaf_hashes(leaves))


def test_empty_and_malformed_batches_are_rejected(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-empty")
    _sender(contract_env, OPERATOR)
    with pytest.raises(UserError, match="at least one leaf"):
        contract.commit_batch("empty", "empty", "[]", "0" * 64, 10)
    with pytest.raises(UserError, match="valid JSON"):
        contract.commit_batch("bad", "bad", "{", "0" * 64, 10)
    with pytest.raises(UserError, match="evidence"):
        contract.commit_batch("no-evidence", "no-evidence", json.dumps([{"leaf_id": "x", "decision": "ACCEPT"}]), "0" * 64, 10)


def test_duplicate_leaf_ids_are_rejected(contract_env):
    leaves = make_leaves()
    leaves[1]["leaf_id"] = leaves[0]["leaf_id"]
    _fund(contract_env, OPERATOR, 10, "fund-duplicate")
    _sender(contract_env, OPERATOR)
    with pytest.raises(UserError, match="duplicate leaf_id"):
        contract_env["contract"].commit_batch("dup", "dup", json.dumps(leaves), _root(leaves), 10)


def test_claimed_root_mismatch_does_not_lock_bond(contract_env):
    _fund(contract_env, OPERATOR, 10, "fund-root")
    _sender(contract_env, OPERATOR)
    leaves = make_leaves()
    with pytest.raises(UserError, match="recomputed Merkle root"):
        contract_env["contract"].commit_batch("bad-root", "bad-root", json.dumps(leaves), "0" * 64, 10)
    assert json.loads(contract_env["contract"].get_bond(OPERATOR))["available"] == "10"


def test_valid_commit_is_idempotent_and_content_bound(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-idem")
    first = _commit(contract_env, action="commit-idem")
    assert json.loads(first)["status"] == "COMMITTED"
    second = _commit(contract_env, action="commit-idem")
    assert json.loads(second)["content_digest"] == json.loads(first)["content_digest"]
    assert json.loads(contract.get_bond(OPERATOR))["locked"] == "10"
    with pytest.raises(UserError, match="action_id"):
        _commit(contract_env, action="commit-idem", leaves=make_leaves()[:2])
    with pytest.raises(UserError, match="different content"):
        _commit(contract_env, batch_id="batch-1", action="other-commit", leaves=make_leaves()[:2])


def test_valid_merkle_proof_and_invalid_proof_are_distinct(contract_env):
    contract = contract_env["contract"]
    leaves = make_leaves()
    _fund(contract_env, OPERATOR, 10, "fund-proof")
    _fund(contract_env, CHALLENGER, 5, "fund-proof-c")
    _commit(contract_env, action="commit-proof")
    bad = _proof(leaves, 1)
    bad[0] = "f" * 64
    with pytest.raises(UserError, match="invalid Merkle"):
        _challenge(contract_env, action="bad-proof", proof=bad)
    assert _status(contract_env) == "COMMITTED"
    assert json.loads(contract.get_bond(CHALLENGER))["locked"] == "0"
    _challenge(contract_env, action="good-proof")
    assert _status(contract_env) == "CHALLENGED"


def test_review_mark_and_retry_replays_are_idempotent(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["INCONCLUSIVE"])
    first_review = _review(contract_env, action="review-replay")
    second_review = _review(contract_env, action="review-replay")
    assert json.loads(first_review) == json.loads(second_review)
    first_retry = contract_env["contract"].retry_review("retry-replay", "batch-1", "challenge-1")
    second_retry = contract_env["contract"].retry_review("retry-replay", "batch-1", "challenge-1")
    assert json.loads(first_retry) == json.loads(second_retry)


def test_mark_unresolved_replay_is_idempotent(contract_env):
    _setup_challenged(contract_env)
    contract_env["clock"]["now"] = 1_051
    first = contract_env["contract"].mark_unresolved("mark-replay", "batch-1", "challenge-1")
    second = contract_env["contract"].mark_unresolved("mark-replay", "batch-1", "challenge-1")
    assert json.loads(first) == json.loads(second)


def test_challenge_replay_survives_expiry(contract_env):
    _setup_challenged(contract_env)
    contract_env["clock"]["now"] = 1_100
    replay = _challenge(contract_env, action="challenge-batch-1")
    assert json.loads(replay)["challenge_id"] == "challenge-1"
    assert _status(contract_env) == "CHALLENGED"


def test_storage_tuple_keys_do_not_alias(contract_env):
    module = contract_env["module"]
    assert module._tuple_key("a:b", "c") != module._tuple_key("a", "b:c")
    assert module._tuple_key("a", "b", "1") != module._tuple_key("a", "b:1")


def test_non_power_of_two_proof_shape_is_rejected(contract_env):
    contract = contract_env["contract"]
    leaves = make_leaves()
    root = _root(leaves)
    assert contract.verify_merkle_proof(
        _sha256(json.dumps(leaves[0], sort_keys=True, separators=(",", ":")).encode()),
        json.dumps(_proof(leaves, 0)),
        root,
        0,
        5,
    ) is False


def test_operator_cannot_challenge_and_second_challenge_is_rejected(contract_env):
    _fund(contract_env, OPERATOR, 15, "fund-self")
    _commit(contract_env, action="commit-self")
    _sender(contract_env, OPERATOR)
    with pytest.raises(UserError, match="own batch"):
        contract_env["contract"].challenge_leaf("self", "batch-1", "c", 0, _sha256(json.dumps(make_leaves()[0], sort_keys=True, separators=(",", ":")).encode()), json.dumps(_proof(make_leaves(), 0)), "reason", 5)
    _fund(contract_env, CHALLENGER, 10, "fund-second")
    _challenge(contract_env, action="first-challenge")
    with pytest.raises(UserError, match="active challenge"):
        _challenge(contract_env, challenge_id="second", index=0, action="second-challenge")


def test_unauthorized_or_duplicate_challenge_is_rejected(contract_env):
    _fund(contract_env, OPERATOR, 10, "fund-unauth")
    _commit(contract_env, action="commit-unauth")
    _fund(contract_env, CHALLENGER, 5, "fund-unauth-c")
    _challenge(contract_env, action="challenge-unauth")
    with pytest.raises(UserError, match="active challenge"):
        _challenge(contract_env, challenge_id="other", index=0, action="challenge-unauth-2")
    with pytest.raises(UserError, match="different arguments"):
        _challenge(contract_env, challenge_id="challenge-1", index=0, action="challenge-unauth-3", reason="changed")


def test_challenge_window_expiry_is_enforced(contract_env):
    _fund(contract_env, OPERATOR, 10, "fund-expired")
    _fund(contract_env, CHALLENGER, 5, "fund-expired-c")
    _commit(contract_env, action="commit-expired")
    contract_env["clock"]["now"] = 1_100
    with pytest.raises(UserError, match="expired"):
        _challenge(contract_env, action="challenge-expired")
    assert _status(contract_env) == "COMMITTED"


def test_uncontested_batch_finalizes_valid_and_refunds(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-final")
    _commit(contract_env, action="commit-final")
    contract_env["clock"]["now"] = 1_100
    record = json.loads(contract.finalize_batch("finalize-valid", "batch-1"))
    assert record["status"] == "FINALIZED_VALID"
    assert record["settlement"]["challenger_reward"] == "0"
    assert json.loads(contract.get_bond(OPERATOR))["available"] == "10"
    assert json.loads(contract.get_bond(OPERATOR))["locked"] == "0"


@pytest.mark.parametrize("outcome,expected", [("SUPPORTED", "UPHELD"), ("CONTRADICTED", "INVALIDATED"), ("INCONCLUSIVE", "UNRESOLVED")])
def test_review_outcomes_have_explicit_application_mapping(contract_env, outcome, expected):
    contract = contract_env["contract"]
    _setup_challenged(contract_env)
    _set_prompt(contract_env, [outcome])
    record = json.loads(_review(contract_env))
    assert record["outcome"] == outcome
    assert record["normalization"] == "SCHEMA_VALIDATED"
    assert "consensus" not in record
    assert _status(contract_env) == expected
    assert "fraud" not in record["reason_code"].lower()
    assert contract.get_fraud_status("batch-1").startswith("NOT_ASSERTED")


def test_malformed_llm_json_is_not_committed_as_a_review(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["MALFORMED"])
    with pytest.raises(ConsensusFailure):
        _review(contract_env)
    assert _status(contract_env) == "CHALLENGED"
    assert contract_env["contract"].get_review("batch-1", "challenge-1", 1) == ""


def test_llm_provider_failure_does_not_change_application_state(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["RAISE"])
    with pytest.raises(RuntimeError, match="provider failure"):
        _review(contract_env)
    assert _status(contract_env) == "CHALLENGED"
    assert contract_env["contract"].get_review("batch-1", "challenge-1", 1) == ""


def test_conflicting_validator_verdicts_leave_state_unchanged(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["CONTRADICTED", "SUPPORTED"])
    with pytest.raises(ConsensusFailure):
        _review(contract_env)
    assert _status(contract_env) == "CHALLENGED"
    assert contract_env["contract"].get_review("batch-1", "challenge-1", 1) == ""


def test_expired_review_becomes_unresolved_without_fraud(contract_env):
    _setup_challenged(contract_env)
    contract_env["clock"]["now"] = 1_051
    with pytest.raises(UserError, match="review window has expired"):
        _review(contract_env)
    record = json.loads(contract_env["contract"].mark_unresolved("mark-1", "batch-1", "challenge-1"))
    assert record["outcome"] == "INCONCLUSIVE"
    assert _status(contract_env) == "UNRESOLVED"
    assert contract_env["contract"].get_fraud_status("batch-1").startswith("NOT_ASSERTED")


def test_inconclusive_review_can_be_retried(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["INCONCLUSIVE"])
    _review(contract_env)
    assert _status(contract_env) == "UNRESOLVED"
    contract_env["contract"].retry_review("retry-inconclusive", "batch-1", "challenge-1")
    assert _status(contract_env) == "CHALLENGED"
    challenge = json.loads(contract_env["contract"].get_challenge("batch-1", "challenge-1"))
    assert challenge["round"] == 2


def test_only_finalized_valid_is_downstream_actionable(contract_env):
    _fund(contract_env, OPERATOR, 10, "fund-actionable")
    _commit(contract_env, action="commit-actionable")
    contract = contract_env["contract"]
    assert contract.is_downstream_actionable("batch-1") is False
    contract_env["clock"]["now"] = 1_100
    contract.finalize_batch("finalize-actionable", "batch-1")
    assert contract.is_downstream_actionable("batch-1") is True


def test_unresolved_can_retry_then_close_with_refunds(contract_env):
    _setup_challenged(contract_env)
    contract_env["clock"]["now"] = 1_050
    contract_env["contract"].mark_unresolved("mark", "batch-1", "challenge-1")
    _sender(contract_env, OTHER)
    contract_env["contract"].retry_review("retry", "batch-1", "challenge-1")
    assert _status(contract_env) == "CHALLENGED"
    contract_env["clock"]["now"] = 1_100
    contract_env["contract"].mark_unresolved("mark-2", "batch-1", "challenge-1")
    contract_env["contract"].close_unresolved("close", "batch-1")
    assert _status(contract_env) == "CANCELED"
    assert json.loads(contract_env["contract"].get_bond(OPERATOR))["available"] == "10"
    assert json.loads(contract_env["contract"].get_bond(CHALLENGER))["available"] == "5"


def test_invalidated_finalization_transfers_reward_without_fraud(contract_env):
    _setup_challenged(contract_env)
    _set_prompt(contract_env, ["CONTRADICTED"])
    _review(contract_env)
    contract_env["clock"]["now"] = 1_100
    record = json.loads(contract_env["contract"].finalize_batch("finalize-invalid", "batch-1"))
    assert record["status"] == "FINALIZED_INVALID"
    assert record["settlement"]["challenger_reward"] == "3"
    assert record["settlement"]["operator_refund"] == "7"
    assert json.loads(contract_env["contract"].get_bond(OPERATOR))["available"] == "7"
    assert json.loads(contract_env["contract"].get_bond(CHALLENGER))["available"] == "8"
    assert contract_env["contract"].get_fraud_status("batch-1").startswith("NOT_ASSERTED")


def test_terminal_state_and_duplicate_actions_are_guarded(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-terminal")
    _commit(contract_env, action="commit-terminal")
    contract_env["clock"]["now"] = 1_100
    first = contract.finalize_batch("finalize", "batch-1")
    second = contract.finalize_batch("finalize", "batch-1")
    assert json.loads(first) == json.loads(second)
    with pytest.raises(UserError, match="already terminal"):
        contract.finalize_batch("finalize-again", "batch-1")
    with pytest.raises(UserError, match="action_id"):
        contract.fund_bond("finalize", OPERATOR, 1)


def test_operator_can_cancel_only_before_challenge(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-cancel")
    _commit(contract_env, action="commit-cancel")
    _sender(contract_env, OTHER)
    with pytest.raises(UserError, match="only the operator"):
        contract.cancel_batch("cancel-unauth", "batch-1")
    _sender(contract_env, OPERATOR)
    record = json.loads(contract.cancel_batch("cancel", "batch-1"))
    assert record["status"] == "CANCELED"
    assert json.loads(contract.get_bond(OPERATOR))["available"] == "10"


def test_bond_credit_is_owner_only_and_idempotent(contract_env):
    contract = contract_env["contract"]
    _fund(contract_env, OPERATOR, 10, "fund-credit")
    before = json.loads(contract.get_bond(OPERATOR))
    _fund(contract_env, OPERATOR, 10, "fund-credit")
    after = json.loads(contract.get_bond(OPERATOR))
    assert after == before
    _fund(contract_env, OPERATOR, 10, "fund-credit-2")
    assert json.loads(contract.get_bond(OPERATOR))["available"] == "20"
    _sender(contract_env, OTHER)
    with pytest.raises(UserError, match="account owner"):
        contract.fund_bond("not-owner", OPERATOR, 1)
