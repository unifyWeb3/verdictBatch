"""Small local GenLayer stand-in used only by the direct contract tests."""

import importlib.util
import json
import re
import sys
import types
from pathlib import Path


class UserError(Exception):
    pass


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class ConsensusFailure(Exception):
    pass


class TreeMap(dict):
    @classmethod
    def __class_getitem__(cls, item):
        return cls


class DynArray(list):
    @classmethod
    def __class_getitem__(cls, item):
        return cls


class Contract:
    pass


class _WriteDecorator:
    def __call__(self, function):
        return function

    def payable(self, function):
        return function


class _Public:
    @staticmethod
    def view(function):
        return function

    write = _WriteDecorator()


def _default_prompt(prompt, **kwargs):
    raise RuntimeError("no prompt fixture configured")


def _run_nondet(leader_fn, validator_fn):
    leader_value = leader_fn()
    if not validator_fn(Return(leader_value)):
        raise ConsensusFailure("validator disagreed")
    return leader_value


def install_genlayer_stub():
    module = types.ModuleType("genlayer")
    module.__all__ = [
        "Contract",
        "DynArray",
        "TreeMap",
        "u32",
        "u64",
        "u256",
        "Address",
    ]
    module.Contract = Contract
    module.TreeMap = TreeMap
    module.DynArray = DynArray
    module.u32 = int
    module.u64 = int
    module.u256 = int
    module.Address = str
    module.public = _Public()

    module.vm = types.SimpleNamespace(
        UserError=UserError,
        Return=Return,
        run_nondet=_run_nondet,
    )
    module.nondet = types.SimpleNamespace(exec_prompt=_default_prompt)
    module.message = types.SimpleNamespace(sender_address="0x" + "00" * 20)
    module.prompt_handler = None
    module.nondet.exec_prompt = lambda prompt, **kwargs: (
        module.prompt_handler(prompt, **kwargs)
        if module.prompt_handler is not None
        else _default_prompt(prompt, **kwargs)
    )
    sys.modules["genlayer"] = module
    return module


def load_contract():
    install_genlayer_stub()
    contract_path = Path(__file__).parents[1] / "contracts" / "verdict_batch.py"
    spec = importlib.util.spec_from_file_location("verdict_batch_under_test", contract_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sys.modules["genlayer"]


def make_policy(challenge_window=100, review_window=50, max_rounds=2):
    return json.dumps(
        {
            "min_operator_bond": 10,
            "min_challenger_bond": 5,
            "challenge_window_seconds": challenge_window,
            "review_window_seconds": review_window,
            "max_review_rounds": max_rounds,
            "max_leaves": 16,
            "reward_on_invalidation": 3,
            "invalidates_on_challenge": True,
            "allow_cancel": True,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def make_leaves():
    return [
        {
            "leaf_id": "leaf-1",
            "decision": "ACCEPT",
            "evidence": "The deliverable includes the required tests and reproduction steps.",
        },
        {
            "leaf_id": "leaf-2",
            "decision": "REJECT",
            "evidence": "The rubric requires a test run, but the submission only contains a README.",
        },
        {
            "leaf_id": "leaf-3",
            "decision": "REJECT",
            "evidence": "Two reviewer notes conflict and the rubric excerpt is incomplete.",
        },
    ]


def digest_from_prompt(prompt):
    input_digest = re.search(r"input_digest: ([0-9a-f]{64})", prompt).group(1)
    evidence_digest = re.search(r"evidence_digest: ([0-9a-f]{64})", prompt).group(1)
    return input_digest, evidence_digest
