"""Patch engine: canonical-data paths, malformed-op errors with index+location."""

import pytest

from sigil.core.ast import from_data, to_data
from sigil.core.patch import PatchError, apply_ops
from sigil.lang.parser import parse_module


def _triple_fn_data():
    mod = parse_module("module m\n\nfn triple(n Int) -> Int\n  pure\n{\n  ret n * 2\n}\n")
    return to_data(mod.defs[0])


def test_replace_constant_via_path() -> None:
    data = _triple_fn_data()
    # body.stmts.0.value.right is the literal 2 -> make it 3
    patched = apply_ops(
        data, [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}]
    )
    fn = from_data(patched)
    assert "ret n * 3" in __import__("sigil.lang.printer", fromlist=["pfn"]).pfn(fn)


def test_untouched_subtrees_are_untouched() -> None:
    data = _triple_fn_data()
    patched = apply_ops(
        data, [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}]
    )
    assert patched["params"] == data["params"]
    assert patched["name"] == data["name"]


def test_malformed_path_names_op_index_and_location() -> None:
    data = _triple_fn_data()
    with pytest.raises(PatchError) as exc:
        apply_ops(
            data,
            [
                {"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"},
                {"path": "body.nonsense.7", "op": "replace", "value": "x"},
            ],
        )
    msg = str(exc.value)
    assert "op #1" in msg and "nonsense" in msg and "Remedy" in msg
    assert exc.value.code == "bad_path"


def test_unknown_op_rejected() -> None:
    with pytest.raises(PatchError) as exc:
        apply_ops(_triple_fn_data(), [{"path": "name", "op": "frobnicate"}])
    assert exc.value.code == "bad_op"


def test_insert_and_delete_in_lists() -> None:
    data = _triple_fn_data()
    stmt = data["body"]["stmts"][0]
    grown = apply_ops(data, [{"path": "body.stmts.0", "op": "insert", "value": stmt}])
    assert len(grown["body"]["stmts"]) == 2
    shrunk = apply_ops(grown, [{"path": "body.stmts.1", "op": "delete"}])
    assert shrunk == data
