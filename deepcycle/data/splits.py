import random
from typing import Any

from deepcycle.data.registry import DatasetSpec


def make_splits(
    *,
    spec: DatasetSpec,
    samples: list[dict[str, Any]],
    seed: int,
    split_policy: str,
) -> dict[str, list[dict[str, Any]]]:
    # If adapters provide an explicit split marker, honor it.
    if any("official_split" in s for s in samples):
        by_split = {"train": [], "val": [], "test": []}
        for s in samples:
            sp = s.get("official_split")
            if sp in by_split:
                by_split[sp].append(s)
        # If all three exist, we're done; otherwise, fall back to policy for remaining.
        if all(len(by_split[k]) > 0 for k in ("train", "val", "test")):
            return by_split

    if split_policy == "existing_else_80_10_10":
        ratios = (0.8, 0.1, 0.1)
    elif split_policy == "80_10_10":
        ratios = (0.8, 0.1, 0.1)
    elif split_policy == "70_15_15":
        ratios = (0.7, 0.15, 0.15)
    else:
        raise ValueError(f"Unknown split_policy: {split_policy}")

    # If group_key exists, do group-aware split to reduce leakage.
    group_key = spec.group_key
    if group_key:
        return _group_split(samples=samples, group_key=group_key, seed=seed, ratios=ratios)

    # Stratify for classification if labels exist.
    if spec.task == "classification" and all("y" in s and int(s.get("y", -1)) >= 0 for s in samples):
        return _stratified_split(samples=samples, seed=seed, ratios=ratios)

    # Fallback: shuffle split.
    rng = random.Random(seed)
    idx = list(range(len(samples)))
    rng.shuffle(idx)
    n = len(samples)
    n_train = int(ratios[0] * n)
    n_val = int(ratios[1] * n)

    train = [samples[i] for i in idx[:n_train]]
    val = [samples[i] for i in idx[n_train : n_train + n_val]]
    test = [samples[i] for i in idx[n_train + n_val :]]

    return {"train": train, "val": val, "test": test}


def _stratified_split(*, samples: list[dict[str, Any]], seed: int, ratios: tuple[float, float, float]):
   rng = random.Random(seed)
   buckets: dict[int, list[dict[str, Any]]] = {}
   for s in samples:
       buckets.setdefault(int(s["y"]), []).append(s)

   train: list[dict[str, Any]] = []
   val: list[dict[str, Any]] = []
   test: list[dict[str, Any]] = []
   for _, items in buckets.items():
       rng.shuffle(items)
       n = len(items)
       n_train = int(ratios[0] * n)
       n_val = int(ratios[1] * n)
       train.extend(items[:n_train])
       val.extend(items[n_train : n_train + n_val])
       test.extend(items[n_train + n_val :])
   rng.shuffle(train)
   rng.shuffle(val)
   rng.shuffle(test)
   return {"train": train, "val": val, "test": test}


def _group_split(*, samples: list[dict[str, Any]], group_key: str, seed: int, ratios: tuple[float, float, float]):
   rng = random.Random(seed)
   groups: dict[str, list[dict[str, Any]]] = {}
   for s in samples:
       g = str(s.get(group_key))
       groups.setdefault(g, []).append(s)

   group_ids = list(groups.keys())
   rng.shuffle(group_ids)

   n_groups = len(group_ids)
   n_train = int(ratios[0] * n_groups)
   n_val = int(ratios[1] * n_groups)

   train_ids = set(group_ids[:n_train])
   val_ids = set(group_ids[n_train : n_train + n_val])
   test_ids = set(group_ids[n_train + n_val :])

   train = [s for g in train_ids for s in groups[g]]
   val = [s for g in val_ids for s in groups[g]]
   test = [s for g in test_ids for s in groups[g]]

   rng.shuffle(train)
   rng.shuffle(val)
   rng.shuffle(test)
   return {"train": train, "val": val, "test": test}
