import pytest

from genlayer_stub import load_contract, make_policy


@pytest.fixture
def contract_env(monkeypatch):
    module, gl = load_contract()
    clock = {"now": 1_000}
    monkeypatch.setattr(module, "_now", lambda: clock["now"])
    contract = module.VerdictBatch("demo-policy", make_policy())
    for field_name in ("batches", "leaves", "challenges", "reviews", "bonds", "actions"):
        setattr(contract, field_name, gl.TreeMap())
    setattr(contract, "batch_order", gl.DynArray())
    gl.message.sender_address = "0x" + "11" * 20
    return {
        "module": module,
        "gl": gl,
        "contract": contract,
        "clock": clock,
        "operator": "0x" + "11" * 20,
        "challenger": "0x" + "22" * 20,
        "other": "0x" + "33" * 20,
    }
