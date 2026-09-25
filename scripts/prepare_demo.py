"""Prepare canonical leaves, a root, and inclusion proofs for Studio calls."""

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def pair(left, right):
    return hashlib.sha256(bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def root_and_proofs(leaves):
    hashes = [digest(leaf) for leaf in leaves]
    size = 1
    while size < len(hashes):
        size *= 2
    padded = hashes + [hashes[-1]] * (size - len(hashes))
    levels = [padded]
    level = padded
    while len(level) > 1:
        level = [pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        levels.append(level)
    proofs = []
    for index in range(len(hashes)):
        current = index
        proof = []
        for level_index in range(len(levels) - 1):
            level = levels[level_index]
            proof.append(level[current ^ 1])
            current //= 2
        proofs.append(proof)
    return padded, levels[-1][0], proofs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("leaves", type=Path)
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    leaves = json.loads(args.leaves.read_text())
    if args.index < 0 or args.index >= len(leaves):
        raise SystemExit("index is outside the leaf list")
    hashes, root, proofs = root_and_proofs(leaves)
    print(json.dumps({
        "leaf_count": len(leaves),
        "tree_leaf_count": len(hashes),
        "root": root,
        "leaf_hash": hashes[args.index],
        "proof": proofs[args.index],
        "leaves_json": canonical(leaves),
    }, indent=2))


if __name__ == "__main__":
    main()
