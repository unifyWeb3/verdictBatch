# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Evidence-gated, leaf-disputable batch adjudication.

Application lifecycle states are deliberately separate from GenLayer protocol
transaction states.  A protocol transaction can be ACCEPTED or FINALIZED while
the application disposition recorded here is COMMITTED, UNRESOLVED, or
FINALIZED_INVALID.

Bonds are an internal v1 ledger.  They are not an escrow claim and no native
value is transferred by this contract.
"""

import datetime
import hashlib
import json

import genlayer as gl
from genlayer import *


COMMITTED = "COMMITTED"
CHALLENGED = "CHALLENGED"
UPHELD = "UPHELD"
INVALIDATED = "INVALIDATED"
UNRESOLVED = "UNRESOLVED"
FINALIZED_VALID = "FINALIZED_VALID"
FINALIZED_INVALID = "FINALIZED_INVALID"
CANCELED = "CANCELED"

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INCONCLUSIVE = "INCONCLUSIVE"

NOT_ASSERTED = "NOT_ASSERTED"
TERMINAL_STATES = (FINALIZED_VALID, FINALIZED_INVALID, CANCELED)
REVIEW_OUTCOMES = (SUPPORTED, CONTRADICTED, INCONCLUSIVE)
ZERO_HASH = "0" * 64
MAX_JSON_BYTES = 200000
MAX_ID_LENGTH = 128
MAX_REASON_LENGTH = 512
U256_MAX = (1 << 256) - 1


def _fail(message: str):
    raise gl.vm.UserError(message)


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_text(value: str) -> str:
    return _sha256_hex(value.encode("utf-8"))


def _now() -> int:
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def _address(value) -> str:
    if hasattr(value, "as_hex"):
        value = value.as_hex
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        _fail("address must be a 20-byte 0x value")
    try:
        int(text[2:], 16)
    except (TypeError, ValueError):
        _fail("address must be hexadecimal")
    return text


def _sender() -> str:
    return _address(gl.message.sender_address)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
        _fail(label + " must be a non-empty string of at most 128 characters")
    return value


def _amount(value) -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        _fail("amount must be an integer")
    if amount <= 0 or amount > U256_MAX:
        _fail("amount must be greater than zero and fit in u256")
    return amount


def _nonnegative_int(value, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        _fail(label + " must be an integer")
    if number < 0 or number > U256_MAX:
        _fail(label + " must be a non-negative integer")
    return number


def _parse_json(value: str, label: str):
    if not isinstance(value, str) or len(value) > MAX_JSON_BYTES:
        _fail(label + " is too large")
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        _fail(label + " must be valid JSON")


def _parse_json_object(value: str, label: str) -> dict:
    parsed = _parse_json(value, label)
    if not isinstance(parsed, dict):
        _fail(label + " must be a JSON object")
    return parsed


def _canonical_leaf(value) -> str:
    if not isinstance(value, dict):
        _fail("each leaf must be a JSON object")
    leaf_id = value.get("leaf_id")
    decision = value.get("decision")
    evidence = value.get("evidence")
    if not isinstance(leaf_id, str) or not leaf_id or len(leaf_id) > MAX_ID_LENGTH:
        _fail("leaf_id must be a non-empty string")
    if not isinstance(decision, str) or not decision or len(decision) > MAX_REASON_LENGTH:
        _fail("leaf decision must be a non-empty string")
    if not isinstance(evidence, str) or not evidence or len(evidence) > MAX_REASON_LENGTH:
        _fail("leaf evidence must be a non-empty string")
    return _canonical_json(value)


def _leaf_hashes(leaves: list) -> list[str]:
    if not isinstance(leaves, list) or not leaves:
        _fail("batch must contain at least one leaf")
    hashes = []
    seen = set()
    for leaf in leaves:
        canonical = _canonical_leaf(leaf)
        leaf_id = leaf["leaf_id"]
        if leaf_id in seen:
            _fail("duplicate leaf_id: " + leaf_id)
        seen.add(leaf_id)
        hashes.append(_hash_text(canonical))
    return hashes


def _tree_leaf_count(leaf_count: int) -> int:
    if leaf_count <= 0 or leaf_count > 1024:
        _fail("leaf_count is outside the supported range")
    padded = 1
    while padded < leaf_count:
        padded *= 2
    return padded


def _merkle_root_from_hashes(leaf_hashes: list[str]) -> str:
    padded_count = _tree_leaf_count(len(leaf_hashes))
    level = list(leaf_hashes)
    while len(level) < padded_count:
        level.append(level[-1])
    while len(level) > 1:
        next_level = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1]
            next_level.append(_hash_bytes32_pair(left, right))
        level = next_level
    return level[0]


def _hash_bytes32_pair(left: str, right: str) -> str:
    try:
        return _sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))
    except (TypeError, ValueError):
        _fail("invalid Merkle node")


def _merkle_proof_from_hashes(leaf_hashes: list[str], leaf_index: int) -> list[str]:
    padded_count = _tree_leaf_count(len(leaf_hashes))
    if leaf_index < 0 or leaf_index >= len(leaf_hashes):
        _fail("leaf_index is outside the batch")
    level = list(leaf_hashes)
    while len(level) < padded_count:
        level.append(level[-1])
    index = leaf_index
    proof = []
    while len(level) > 1:
        sibling_index = index ^ 1
        proof.append(level[sibling_index])
        next_level = []
        for position in range(0, len(level), 2):
            next_level.append(_hash_bytes32_pair(level[position], level[position + 1]))
        level = next_level
        index = index // 2
    return proof


def _verify_proof(leaf_hash: str, proof: list[str], root: str, leaf_index: int, tree_leaf_count: int) -> bool:
    if not isinstance(proof, list) or not isinstance(leaf_hash, str) or not isinstance(root, str):
        return False
    if len(leaf_hash) != 64 or len(root) != 64:
        return False
    if leaf_index < 0 or tree_leaf_count <= 0 or leaf_index >= tree_leaf_count:
        return False
    expected_length = 0
    size = tree_leaf_count
    while size > 1:
        expected_length += 1
        size //= 2
    if len(proof) != expected_length:
        return False
    current = leaf_hash.lower()
    index = leaf_index
    try:
        for sibling in proof:
            if not isinstance(sibling, str) or len(sibling) != 64:
                return False
            sibling = sibling.lower()
            if index % 2 == 0:
                current = _hash_bytes32_pair(current, sibling)
            else:
                current = _hash_bytes32_pair(sibling, current)
            index //= 2
    except gl.vm.UserError:
        return False
    return current == root.lower()


def _policy_defaults(policy_id: str, policy: dict) -> dict:
    required = (
        "min_operator_bond",
        "min_challenger_bond",
        "challenge_window_seconds",
        "review_window_seconds",
        "max_review_rounds",
        "max_leaves",
        "reward_on_invalidation",
    )
    for key in required:
        if key not in policy:
            _fail("policy is missing " + key)
    if policy.get("invalidates_on_challenge", True) is not True:
        _fail("v1 policy must invalidate on a contradicted decision")
    if policy.get("allow_cancel", True) is not True:
        _fail("v1 policy must allow cancellation")
    result = dict(policy)
    result["policy_id"] = policy_id
    result["min_operator_bond"] = str(_nonnegative_int(policy["min_operator_bond"], "min_operator_bond"))
    result["min_challenger_bond"] = str(_nonnegative_int(policy["min_challenger_bond"], "min_challenger_bond"))
    result["challenge_window_seconds"] = str(_nonnegative_int(policy["challenge_window_seconds"], "challenge_window_seconds"))
    result["review_window_seconds"] = str(_nonnegative_int(policy["review_window_seconds"], "review_window_seconds"))
    result["max_review_rounds"] = str(_nonnegative_int(policy["max_review_rounds"], "max_review_rounds"))
    result["max_leaves"] = str(_nonnegative_int(policy["max_leaves"], "max_leaves"))
    result["reward_on_invalidation"] = str(_nonnegative_int(policy["reward_on_invalidation"], "reward_on_invalidation"))
    if int(result["min_operator_bond"]) <= 0 or int(result["min_challenger_bond"]) <= 0:
        _fail("policy bonds must be greater than zero")
    if int(result["challenge_window_seconds"]) <= 0 or int(result["review_window_seconds"]) <= 0:
        _fail("policy windows must be greater than zero")
    if int(result["max_review_rounds"]) <= 0 or int(result["max_leaves"]) <= 0:
        _fail("policy limits must be greater than zero")
    return result


def _new_bond() -> dict:
    return {
        "available": "0",
        "locked": "0",
        "deposited": "0",
        "reward_received": "0",
        "refunded": "0",
    }


def _bond_json(contract, account: str) -> dict:
    raw = contract.bonds.get(account, "")
    if not raw:
        return _new_bond()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        _fail("bond ledger is corrupt")
    for key, value in _new_bond().items():
        if key not in parsed:
            parsed[key] = value
    return parsed


def _save_bond(contract, account: str, ledger: dict):
    contract.bonds[account] = _canonical_json(ledger)


def _add(ledger: dict, key: str, amount: int):
    ledger[key] = str(int(ledger.get(key, "0")) + amount)


def _sub(ledger: dict, key: str, amount: int):
    current = int(ledger.get(key, "0"))
    if current < amount:
        _fail("insufficient internal bond balance")
    ledger[key] = str(current - amount)


def _lock(contract, account: str, amount: int):
    ledger = _bond_json(contract, account)
    _sub(ledger, "available", amount)
    _add(ledger, "locked", amount)
    _save_bond(contract, account, ledger)


def _return_locked(contract, account: str, amount: int):
    ledger = _bond_json(contract, account)
    _sub(ledger, "locked", amount)
    _add(ledger, "available", amount)
    _add(ledger, "refunded", amount)
    _save_bond(contract, account, ledger)


def _reward_locked(contract, from_account: str, to_account: str, amount: int):
    if amount <= 0:
        return
    source = _bond_json(contract, from_account)
    _sub(source, "locked", amount)
    _save_bond(contract, from_account, source)
    target = _bond_json(contract, to_account)
    _add(target, "available", amount)
    _add(target, "reward_received", amount)
    _save_bond(contract, to_account, target)


def _batch(contract, batch_id: str) -> dict:
    raw = contract.batches.get(batch_id, "")
    if not raw:
        _fail("unknown batch")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        _fail("batch record is corrupt")
    return parsed


def _challenge(contract, batch_id: str, challenge_id: str) -> dict:
    raw = contract.challenges.get(batch_id + ":" + challenge_id, "")
    if not raw:
        _fail("unknown challenge")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        _fail("challenge record is corrupt")
    return parsed


def _leaf(contract, batch_id: str, index: int) -> dict:
    raw = contract.leaves.get(batch_id + ":" + str(index), "")
    if not raw:
        _fail("unknown leaf")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        _fail("leaf record is corrupt")
    return parsed


def _action_digest(kind: str, payload: dict) -> str:
    return _hash_text(_canonical_json({"kind": kind, "payload": payload}))


def _action_replay(contract, action_id: str, digest: str) -> bool:
    _id(action_id, "action_id")
    raw = contract.actions.get(action_id, "")
    if not raw:
        return False
    record = json.loads(raw)
    if not isinstance(record, dict) or record.get("digest") != digest:
        _fail("action_id was already used with different arguments")
    return True


def _record_action(contract, action_id: str, digest: str, result: str):
    contract.actions[action_id] = _canonical_json({"digest": digest, "result": result})


def _parse_policy(policy_id: str, policy_json: str) -> dict:
    _id(policy_id, "policy_id")
    parsed = _parse_json_object(policy_json, "policy_json")
    return _policy_defaults(policy_id, parsed)


def _normalize_review(raw, input_digest: str, evidence_digest: str) -> dict:
    neutral = {
        "outcome": INCONCLUSIVE,
        "reason_code": "MALFORMED_OUTPUT",
        "input_digest": input_digest,
        "evidence_digest": evidence_digest,
    }
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return neutral
    if not isinstance(raw, dict):
        return neutral
    outcome = raw.get("outcome")
    reason_code = raw.get("reason_code")
    if not isinstance(outcome, str) or outcome not in REVIEW_OUTCOMES:
        return neutral
    if raw.get("input_digest") != input_digest or raw.get("evidence_digest") != evidence_digest:
        return {
            "outcome": INCONCLUSIVE,
            "reason_code": "DIGEST_MISMATCH",
            "input_digest": input_digest,
            "evidence_digest": evidence_digest,
        }
    if not isinstance(reason_code, str) or not reason_code or len(reason_code) > 64:
        reason_code = "UNSPECIFIED"
    return {
        "outcome": outcome,
        "reason_code": reason_code,
        "input_digest": input_digest,
        "evidence_digest": evidence_digest,
    }


class VerdictBatch(gl.Contract):
    """A policy-driven batch with one active leaf challenge in v1."""

    policy_id: str
    policy_json: str
    policy_hash: str
    batches: TreeMap[str, str]
    leaves: TreeMap[str, str]
    challenges: TreeMap[str, str]
    reviews: TreeMap[str, str]
    bonds: TreeMap[str, str]
    actions: TreeMap[str, str]
    batch_order: DynArray[str]

    def __init__(self, policy_id: str, policy_json: str):
        policy = _parse_policy(policy_id, policy_json)
        canonical_policy = _canonical_json(policy)
        self.policy_id = policy_id
        self.policy_json = canonical_policy
        self.policy_hash = _hash_text(canonical_policy)

    @gl.public.view
    def get_policy(self) -> str:
        return self.policy_json

    @gl.public.view
    def get_policy_hash(self) -> str:
        return self.policy_hash

    @gl.public.view
    def get_fraud_status(self, batch_id: str) -> str:
        batch = _batch(self, batch_id)
        return batch.get("fraud_status", NOT_ASSERTED) + ": application verdicts are not fraud findings"

    @gl.public.view
    def get_batch(self, batch_id: str) -> str:
        return self.batches.get(batch_id, "")

    @gl.public.view
    def get_batch_status(self, batch_id: str) -> str:
        return _batch(self, batch_id).get("status", "")

    @gl.public.view
    def get_leaf(self, batch_id: str, leaf_index: u32) -> str:
        return self.leaves.get(batch_id + ":" + str(int(leaf_index)), "")

    @gl.public.view
    def get_challenge(self, batch_id: str, challenge_id: str) -> str:
        return self.challenges.get(batch_id + ":" + challenge_id, "")

    @gl.public.view
    def get_review(self, batch_id: str, challenge_id: str, review_round: u32) -> str:
        return self.reviews.get(batch_id + ":" + challenge_id + ":" + str(int(review_round)), "")

    @gl.public.view
    def get_bond(self, account: str) -> str:
        return _canonical_json(_bond_json(self, _address(account)))

    @gl.public.view
    def get_action(self, action_id: str) -> str:
        return self.actions.get(action_id, "")

    @gl.public.view
    def compute_merkle_root(self, leaves_json: str) -> str:
        leaves = _parse_json(leaves_json, "leaves_json")
        return _merkle_root_from_hashes(_leaf_hashes(leaves))

    @gl.public.view
    def verify_merkle_proof(self, leaf_hash: str, proof_json: str, root: str, leaf_index: u32, tree_leaf_count: u32) -> bool:
        proof = _parse_json(proof_json, "proof_json")
        return _verify_proof(leaf_hash, proof, root, int(leaf_index), int(tree_leaf_count))

    @gl.public.write
    def fund_bond(self, action_id: str, account: str, amount: u256) -> str:
        account = _address(account)
        if account != _sender():
            _fail("only the account owner can fund its bond")
        amount = _amount(amount)
        digest = _action_digest("fund_bond", {"account": account, "amount": str(amount)})
        if _action_replay(self, action_id, digest):
            return self.actions.get(action_id, "")
        ledger = _bond_json(self, account)
        _add(ledger, "available", amount)
        _add(ledger, "deposited", amount)
        _save_bond(self, account, ledger)
        result = _canonical_json(ledger)
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def commit_batch(self, action_id: str, batch_id: str, leaves_json: str, claimed_root: str, bond_amount: u256) -> str:
        batch_id = _id(batch_id, "batch_id")
        leaves = _parse_json(leaves_json, "leaves_json")
        leaf_hashes = _leaf_hashes(leaves)
        policy = json.loads(self.policy_json)
        if len(leaves) > int(policy["max_leaves"]):
            _fail("batch exceeds policy max_leaves")
        root = _merkle_root_from_hashes(leaf_hashes)
        if not isinstance(claimed_root, str) or claimed_root.lower() != root:
            _fail("claimed_root does not match the recomputed Merkle root")
        bond_amount = _amount(bond_amount)
        if bond_amount < int(policy["min_operator_bond"]):
            _fail("bond_amount is below the policy minimum")
        canonical_leaves = [_canonical_leaf(leaf) for leaf in leaves]
        content_digest = _hash_text(_canonical_json({"leaves": canonical_leaves, "root": root}))
        digest = _action_digest("commit_batch", {
            "batch_id": batch_id,
            "content_digest": content_digest,
            "bond_amount": str(bond_amount),
        })
        if _action_replay(self, action_id, digest):
            return self.batches.get(batch_id, "")
        existing_raw = self.batches.get(batch_id, "")
        if existing_raw:
            existing = json.loads(existing_raw)
            if existing.get("content_digest") != content_digest:
                _fail("batch_id already exists with different content")
            _record_action(self, action_id, digest, existing_raw)
            return existing_raw
        operator = _sender()
        _lock(self, operator, bond_amount)
        created_at = _now()
        challenge_deadline = created_at + int(policy["challenge_window_seconds"])
        batch = {
            "batch_id": batch_id,
            "operator": operator,
            "status": COMMITTED,
            "policy_id": self.policy_id,
            "policy_hash": self.policy_hash,
            "leaf_count": len(leaves),
            "tree_leaf_count": _tree_leaf_count(len(leaves)),
            "root": root,
            "content_digest": content_digest,
            "operator_bond": str(bond_amount),
            "challenger_bond": "0",
            "created_at": created_at,
            "challenge_deadline": challenge_deadline,
            "review_deadline": challenge_deadline,
            "unresolved_deadline": challenge_deadline,
            "version": 1,
            "active_challenge_id": "",
            "settled": False,
            "fraud_status": NOT_ASSERTED,
        }
        self.batches[batch_id] = _canonical_json(batch)
        for index, leaf in enumerate(leaves):
            self.leaves[batch_id + ":" + str(index)] = _canonical_json({
                "index": index,
                "leaf_id": leaf["leaf_id"],
                "canonical": canonical_leaves[index],
                "leaf_hash": leaf_hashes[index],
            })
        self.batch_order.append(batch_id)
        result = self.batches.get(batch_id, "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def challenge_leaf(self, action_id: str, batch_id: str, challenge_id: str, leaf_index: u32, leaf_hash: str, proof_json: str, reason: str, bond_amount: u256) -> str:
        batch_id = _id(batch_id, "batch_id")
        challenge_id = _id(challenge_id, "challenge_id")
        batch = _batch(self, batch_id)
        challenger = _sender()
        if challenger == batch.get("operator"):
            _fail("operator cannot challenge its own batch")
        now = _now()
        if now >= int(batch["challenge_deadline"]):
            _fail("challenge window has expired")
        proof = _parse_json(proof_json, "proof_json")
        if not isinstance(reason, str) or not reason or len(reason) > MAX_REASON_LENGTH:
            _fail("reason must be a non-empty string")
        bond_amount = _amount(bond_amount)
        if bond_amount < int(json.loads(self.policy_json)["min_challenger_bond"]):
            _fail("bond_amount is below the policy minimum")
        leaf = _leaf(self, batch_id, int(leaf_index))
        if not isinstance(leaf_hash, str) or leaf_hash.lower() != leaf["leaf_hash"]:
            _fail("leaf_hash does not match the committed leaf")
        if not _verify_proof(leaf["leaf_hash"], proof, batch["root"], int(leaf_index), int(batch["tree_leaf_count"])):
            _fail("invalid Merkle inclusion proof")
        payload = {
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "leaf_index": int(leaf_index),
            "leaf_hash": leaf["leaf_hash"],
            "proof": proof,
            "reason": reason,
            "bond_amount": str(bond_amount),
        }
        digest = _action_digest("challenge_leaf", payload)
        challenge_key = batch_id + ":" + challenge_id
        existing_challenge = self.challenges.get(challenge_key, "")
        if _action_replay(self, action_id, digest):
            return existing_challenge or self.challenges.get(challenge_key, "")
        if existing_challenge:
            existing = json.loads(existing_challenge)
            if existing.get("payload_digest") != _action_digest("challenge_payload", payload):
                _fail("challenge_id already exists with different arguments")
            _record_action(self, action_id, digest, existing_challenge)
            return existing_challenge
        if batch.get("active_challenge_id"):
            _fail("batch already has an active challenge")
        if batch.get("status") != COMMITTED:
            _fail("batch is not open for challenges")
        if batch.get("settled"):
            _fail("batch is already settled")
        _lock(self, challenger, bond_amount)
        created_at = now
        review_deadline = now + int(json.loads(self.policy_json)["review_window_seconds"])
        challenge = {
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "challenger": challenger,
            "leaf_index": int(leaf_index),
            "leaf_hash": leaf["leaf_hash"],
            "proof": proof,
            "reason": reason,
            "bond_amount": str(bond_amount),
            "round": 1,
            "status": "ACTIVE",
            "outcome": "",
            "created_at": created_at,
            "review_deadline": review_deadline,
            "payload_digest": _action_digest("challenge_payload", payload),
        }
        self.challenges[challenge_key] = _canonical_json(challenge)
        batch["status"] = CHALLENGED
        batch["active_challenge_id"] = challenge_id
        batch["challenger_bond"] = str(bond_amount)
        batch["review_deadline"] = review_deadline
        batch["unresolved_deadline"] = review_deadline
        batch["version"] = int(batch["version"]) + 1
        self.batches[batch_id] = _canonical_json(batch)
        result = self.challenges.get(challenge_key, "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def review_challenge(self, action_id: str, batch_id: str, challenge_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        challenge_id = _id(challenge_id, "challenge_id")
        batch = _batch(self, batch_id)
        challenge = _challenge(self, batch_id, challenge_id)
        if batch.get("status") != CHALLENGED or batch.get("active_challenge_id") != challenge_id:
            _fail("batch is not awaiting this challenge review")
        if challenge.get("status") != "ACTIVE":
            _fail("challenge is not active")
        now = _now()
        if now >= int(batch["review_deadline"]):
            _fail("review window has expired; mark the challenge unresolved")
        review_round = int(challenge["round"])
        leaf = _leaf(self, batch_id, int(challenge["leaf_index"]))
        input_digest = _hash_text(_canonical_json({
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "round": review_round,
            "leaf": leaf["canonical"],
            "policy_hash": self.policy_hash,
        }))
        evidence_digest = _hash_text(leaf["canonical"])
        policy = self.policy_json
        prompt = (
            "Review one committed decision under the supplied policy. "
            "Return only JSON with keys outcome, reason_code, input_digest, evidence_digest. "
            "outcome must be SUPPORTED, CONTRADICTED, or INCONCLUSIVE. "
            "SUPPORTED means the original decision is supported by the declared policy and evidence. "
            "CONTRADICTED means the original decision is invalid under the declared policy and evidence. "
            "INCONCLUSIVE means the evidence is missing, conflicting, ambiguous, or insufficient. "
            "Never call a model disagreement fraud. Compare the decision field, not prose. "
            "Echo input_digest and evidence_digest exactly. reason_code must be a short machine token. "
            "Policy: " + policy + " Committed leaf: " + leaf["canonical"] +
            " input_digest: " + input_digest + " evidence_digest: " + evidence_digest
        )
        digest = _action_digest("review_challenge", {
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "round": review_round,
            "input_digest": input_digest,
        })
        if _action_replay(self, action_id, digest):
            return self.reviews.get(batch_id + ":" + challenge_id + ":" + str(review_round), "")
        if self.reviews.get(batch_id + ":" + challenge_id + ":" + str(review_round), ""):
            _fail("review for this round already exists")

        def leader_fn():
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            return _normalize_review(raw, input_digest, evidence_digest)

        def validator_fn(leader_result):
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_review = leader_result.calldata
            if not isinstance(leader_review, dict):
                return False
            my_review = leader_fn()
            if not isinstance(my_review, dict):
                return False
            return (
                leader_review.get("outcome") == my_review.get("outcome")
                and leader_review.get("input_digest") == my_review.get("input_digest")
                and leader_review.get("evidence_digest") == my_review.get("evidence_digest")
            )

        review = gl.vm.run_nondet(leader_fn, validator_fn)
        if not isinstance(review, dict) or review.get("input_digest") != input_digest:
            _fail("review did not return a normalized decision")
        outcome = review.get("outcome")
        if outcome not in REVIEW_OUTCOMES:
            _fail("review outcome is outside the allowed enum")
        record = {
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "round": review_round,
            "outcome": outcome,
            "reason_code": review.get("reason_code", "UNSPECIFIED"),
            "input_digest": input_digest,
            "evidence_digest": evidence_digest,
            "consensus": "ACCEPTED",
        }
        review_key = batch_id + ":" + challenge_id + ":" + str(review_round)
        self.reviews[review_key] = _canonical_json(record)
        challenge["outcome"] = outcome
        challenge["status"] = "REVIEWED"
        if outcome == SUPPORTED:
            batch["status"] = UPHELD
        elif outcome == CONTRADICTED:
            batch["status"] = INVALIDATED
        else:
            batch["status"] = UNRESOLVED
            batch["unresolved_deadline"] = now + int(json.loads(self.policy_json)["review_window_seconds"])
        batch["version"] = int(batch["version"]) + 1
        self.batches[batch_id] = _canonical_json(batch)
        self.challenges[batch_id + ":" + challenge_id] = _canonical_json(challenge)
        result = self.reviews.get(review_key, "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def mark_unresolved(self, action_id: str, batch_id: str, challenge_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        challenge_id = _id(challenge_id, "challenge_id")
        batch = _batch(self, batch_id)
        challenge = _challenge(self, batch_id, challenge_id)
        if batch.get("status") != CHALLENGED or batch.get("active_challenge_id") != challenge_id:
            _fail("batch is not awaiting this challenge")
        if challenge.get("status") != "ACTIVE":
            _fail("challenge is not active")
        now = _now()
        if now < int(batch["review_deadline"]):
            _fail("review window has not expired")
        digest = _action_digest("mark_unresolved", {"batch_id": batch_id, "challenge_id": challenge_id})
        if _action_replay(self, action_id, digest):
            return self.reviews.get(batch_id + ":" + challenge_id + ":" + str(challenge["round"]), "")
        review_round = int(challenge["round"])
        record = {
            "batch_id": batch_id,
            "challenge_id": challenge_id,
            "round": review_round,
            "outcome": INCONCLUSIVE,
            "reason_code": "NO_CONSENSUS_OR_EXPIRED",
            "consensus": "EXPIRED",
        }
        self.reviews[batch_id + ":" + challenge_id + ":" + str(review_round)] = _canonical_json(record)
        challenge["status"] = "UNRESOLVED"
        challenge["outcome"] = INCONCLUSIVE
        batch["status"] = UNRESOLVED
        batch["unresolved_deadline"] = now + int(json.loads(self.policy_json)["review_window_seconds"])
        batch["version"] = int(batch["version"]) + 1
        self.batches[batch_id] = _canonical_json(batch)
        self.challenges[batch_id + ":" + challenge_id] = _canonical_json(challenge)
        result = self.reviews.get(batch_id + ":" + challenge_id + ":" + str(review_round), "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def retry_review(self, action_id: str, batch_id: str, challenge_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        challenge_id = _id(challenge_id, "challenge_id")
        batch = _batch(self, batch_id)
        challenge = _challenge(self, batch_id, challenge_id)
        if batch.get("status") != UNRESOLVED:
            _fail("batch is not unresolved")
        if challenge.get("status") != "UNRESOLVED":
            _fail("challenge is not unresolved")
        policy = json.loads(self.policy_json)
        if int(challenge["round"]) >= int(policy["max_review_rounds"]):
            _fail("maximum review rounds reached")
        if _now() >= int(batch["unresolved_deadline"]):
            _fail("unresolved retry window has expired")
        digest = _action_digest("retry_review", {"batch_id": batch_id, "challenge_id": challenge_id, "round": int(challenge["round"]) + 1})
        if _action_replay(self, action_id, digest):
            return self.challenges.get(batch_id + ":" + challenge_id, "")
        challenge["round"] = int(challenge["round"]) + 1
        challenge["status"] = "ACTIVE"
        challenge["outcome"] = ""
        batch["status"] = CHALLENGED
        batch["review_deadline"] = _now() + int(policy["review_window_seconds"])
        batch["unresolved_deadline"] = batch["review_deadline"]
        batch["version"] = int(batch["version"]) + 1
        self.batches[batch_id] = _canonical_json(batch)
        self.challenges[batch_id + ":" + challenge_id] = _canonical_json(challenge)
        result = self.challenges.get(batch_id + ":" + challenge_id, "")
        _record_action(self, action_id, digest, result)
        return result

    def _settle(self, batch: dict, final_status: str):
        if batch.get("settled"):
            return
        operator = batch.get("operator", "")
        operator_bond = int(batch.get("operator_bond", "0"))
        challenger_bond = int(batch.get("challenger_bond", "0"))
        challenger = ""
        if batch.get("active_challenge_id"):
            challenger = _challenge(self, batch["batch_id"], batch["active_challenge_id"]).get("challenger", "")
        reward = 0
        if final_status == FINALIZED_INVALID and challenger:
            reward = min(operator_bond, int(json.loads(self.policy_json)["reward_on_invalidation"]))
        operator_refund = operator_bond - reward
        if operator_bond:
            if reward:
                _reward_locked(self, operator, challenger, reward)
            _return_locked(self, operator, operator_refund)
        if challenger_bond and challenger:
            _return_locked(self, challenger, challenger_bond)
        batch["status"] = final_status
        batch["settled"] = True
        batch["settled_at"] = _now()
        batch["settlement"] = {
            "operator_refund": str(operator_refund),
            "challenger_refund": str(challenger_bond),
            "challenger_reward": str(reward),
            "operator_bond": str(operator_bond),
            "challenger_bond": str(challenger_bond),
        }
        batch["version"] = int(batch["version"]) + 1
        self.batches[batch["batch_id"]] = _canonical_json(batch)

    @gl.public.write
    def finalize_batch(self, action_id: str, batch_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        batch = _batch(self, batch_id)
        digest = _action_digest("finalize_batch", {"batch_id": batch_id})
        if _action_replay(self, action_id, digest):
            return self.batches.get(batch_id, "")
        status = batch.get("status")
        if status in TERMINAL_STATES:
            _fail("batch is already terminal")
        if status not in (COMMITTED, UPHELD, INVALIDATED):
            _fail("batch cannot be finalized from its current application state")
        if status == COMMITTED and _now() < int(batch["challenge_deadline"]):
            _fail("challenge window is still open")
        if status in (UPHELD, INVALIDATED) and _now() < int(batch["review_deadline"]):
            _fail("review window is still open")
        final_status = FINALIZED_INVALID if status == INVALIDATED else FINALIZED_VALID
        self._settle(batch, final_status)
        result = self.batches.get(batch_id, "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def cancel_batch(self, action_id: str, batch_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        batch = _batch(self, batch_id)
        if _sender() != batch.get("operator"):
            _fail("only the operator can cancel a batch")
        digest = _action_digest("cancel_batch", {"batch_id": batch_id})
        if _action_replay(self, action_id, digest):
            return self.batches.get(batch_id, "")
        if batch.get("status") != COMMITTED or batch.get("active_challenge_id"):
            _fail("only an unchallenged committed batch can be canceled")
        if _now() >= int(batch["challenge_deadline"]):
            _fail("cancellation window has expired")
        self._settle(batch, CANCELED)
        result = self.batches.get(batch_id, "")
        _record_action(self, action_id, digest, result)
        return result

    @gl.public.write
    def close_unresolved(self, action_id: str, batch_id: str) -> str:
        batch_id = _id(batch_id, "batch_id")
        batch = _batch(self, batch_id)
        digest = _action_digest("close_unresolved", {"batch_id": batch_id})
        if _action_replay(self, action_id, digest):
            return self.batches.get(batch_id, "")
        if batch.get("status") != UNRESOLVED:
            _fail("batch is not unresolved")
        challenge = _challenge(self, batch_id, batch["active_challenge_id"])
        policy = json.loads(self.policy_json)
        expired = _now() >= int(batch["unresolved_deadline"])
        rounds_exhausted = int(challenge["round"]) >= int(policy["max_review_rounds"])
        if not expired and not rounds_exhausted:
            _fail("unresolved batch is still retryable")
        self._settle(batch, CANCELED)
        result = self.batches.get(batch_id, "")
        _record_action(self, action_id, digest, result)
        return result
