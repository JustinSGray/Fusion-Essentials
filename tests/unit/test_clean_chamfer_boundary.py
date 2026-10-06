# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Clean Chamfer's boundary-chain placement, as a pure function over (start, end) vertex pairs."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def boundary():
    source = Path(__file__).parents[2] / "commands" / "cleanChamfer" / "boundary.py"
    spec = importlib.util.spec_from_file_location("clean_chamfer_boundary", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connected(a, b):
    return bool(set(a) & set(b))


def test_edges_extend_both_chains_at_either_end(boundary):
    chain_1, chain_2 = [("a", "b"), ("b", "c")], [("p", "q")]
    left = boundary.place_boundary_edges([("q", "r"), ("z", "a"), ("c", "d")], chain_1, chain_2, _connected)
    assert left == []
    assert chain_1 == [("z", "a"), ("a", "b"), ("b", "c"), ("c", "d")]
    assert chain_2 == [("p", "q"), ("q", "r")]


def test_an_edge_reachable_only_after_another_is_placed_on_a_later_pass(boundary):
    chain_1, chain_2 = [("a", "b")], [("p", "q")]
    left = boundary.place_boundary_edges([("c", "d"), ("b", "c")], chain_1, chain_2, _connected)
    assert left == []
    assert chain_1 == [("a", "b"), ("b", "c"), ("c", "d")]


def test_an_inner_loop_edge_is_returned_instead_of_looping_forever(boundary):
    chain_1, chain_2 = [("a", "b")], [("p", "q")]
    hole = ("h", "h")
    left = boundary.place_boundary_edges([("b", "c"), hole], chain_1, chain_2, _connected)
    assert left == [hole]
    assert chain_1 == [("a", "b"), ("b", "c")] and chain_2 == [("p", "q")]


def test_the_refusal_names_the_unplaced_count_and_the_remedy(boundary):
    assert boundary.unplaced_message(1) == (
        "1 boundary edge(s) connect to neither chain (an inner loop or branched boundary). "
        "Remove the inner loop or select faces whose boundary is two open chains.")
