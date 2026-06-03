from glob import glob
import json
import os
import argparse
import math
from collections import defaultdict

try:
    from itertools import batched
except ImportError:
    # For Python versions < 3.12, define a simple batched function
    def batched(iterable, n):
        """Batch data into lists of length n. The last batch may be shorter."""
        if n < 1:
            raise ValueError("Batch size must be at least one.")
        batch = []
        for item in iterable:
            batch.append(item)
            if len(batch) == n:
                yield batch
                batch = []
        if batch:
            yield batch

def main(args):
    all_examples = glob("./evaluation_examples/*/**/*.json", recursive=True)

    categories = [example.replace("./evaluation_examples/", "") for example in all_examples]
    categories = [os.path.dirname(category) for category in categories]
    categories = list(sorted(set(categories)))

    if not args.use_macarena and not args.use_all:
        categories = [category for category in categories if not category.startswith("macarena/")]

    if not args.use_external and not args.use_all:
        categories = [category for category in categories if not category.startswith("osworld/") and not category.startswith("macosworld/")]

    # find all tasks from selected categories and split them into N machines
    all_tasks = []
    for category in categories:
        examples = [example for example in all_examples if f"/{category}/" in example]
        examples = [(category, os.path.basename(example).replace(".json", "")) for example in examples]
        all_tasks.extend(examples)

    all_tasks.sort()

    machine = 0
    for task_ids in batched(all_tasks, math.ceil(len(all_tasks) / args.number_of_machines)):
        sample = defaultdict(list)

        for category, task_id in task_ids:
            sample[category].append(task_id)
        
        if args.create_small:
            for category in sample:
                sample[category] = sample[category][:3]

        with open(f"./evaluation_examples/machine_{machine}_test.json", "w") as f:
            json.dump(sample, f, indent=4)

        machine += 1


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--number_of_machines", type=int, default=2, help="Number of machines used.")
    parser.add_argument("--use_macarena", action="store_true", help="Whether to use MacArena implementation.")
    parser.add_argument("--use_external", action="store_true", help="Whether to use external implementations (osworld/macosworld).")
    parser.add_argument("--use_all", action="store_true", help="Whether to use all categories.")
    parser.add_argument("--create_small", action="store_true", help="Whether to create a small sample (3 examples per category).")

    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    main(args)
