import os
import json
import logging
import datetime
import argparse
from glob import glob
from pathlib import Path

from desktop_env.desktop_env import DesktopEnv
from runners.lib_run_single import setup_logger

from desktop_env.providers.utm.provider import IPAddressResolutionError

logging.basicConfig(level=logging.DEBUG)

def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Run macOS evaluation examples")
    parser.add_argument(
        "--vm_name", 
        type=str, 
        default="osworld",
        help="Name of the VM"
    )
    parser.add_argument(
        "--id",
        type=int,
        default=0,
        help="ID of the first example to run (default: 0)"
    )
    parser.add_argument(
        "--dir",
        type=str,
        help="Directory to get evaluation examples"
    )
    
    args = parser.parse_args()

    # Load evaluation examples
    examples = sorted(
        glob(os.path.join(args.dir, "**", "*.json"), recursive=True)
    )
    idx = args.id

    try:
        with DesktopEnv(
            action_space="pyautogui",
            provider_name="utm",
            path_to_vm=args.vm_name,
            snapshot_name=args.vm_name
        ) as env:
            while idx < len(examples):
                example_path = examples[idx]

                with open(example_path, "r") as f:
                    example = json.load(f)

                # Override example ID for caching results
                example_result_dir = Path("cache") / example["id"]
                os.makedirs(example_result_dir, exist_ok=True)

                # Setup logger
                runtime_logger = setup_logger(example, example_result_dir)

                runtime_logger.info(f"Example {idx + 1}/{len(examples)}: {example_path}")
                runtime_logger.info(f"Instruction: {example['instruction']}")

                end = False

                if "evaluator" not in example:
                    print(f"Skipping {example_path} as it lacks an evaluator.")
                    end = True

                if not end and isinstance(example["evaluator"], dict) and example["evaluator"].get("func") == "infeasible":
                    runtime_logger.info(f"Example {idx + 1}/{len(examples)}: {example_path} is infeasible, skipping...")
                    end = True
                
                if not end:
                    # os.system(f"code {example_path}")
                    # Reset environment with task configuration
                    obs = env.reset(task_config=example)

                    # Example of waiting step:
                    obs, reward, done, info = env.step("WAIT", pause=5)

                    # Uncomment this block if screenshot saving is needed:
                    step_idx = 0
                    action_timestamp = datetime.datetime.now().strftime("%Y.%m.%d@%H.%M.%S")
                    screenshot_path = example_result_dir / f"step_{step_idx + 1}_{action_timestamp}.png"
                    with open(screenshot_path, "wb") as f:
                        f.write(obs["screenshot"])

                # Interactive loop
                while True:
                    idx += 1
            
                    user_input = input("Press Enter to evaluate, q to quit, n to go to next, r to try again ... ").strip().lower()
                    runtime_logger.debug(f"User input: '{user_input}'")

                    if user_input == "q":
                        exit(0)
                    elif user_input == "n":
                        os.system("clear")
                        idx += 1
                        break
                    elif user_input == "":
                        print(env.evaluate())
                    elif user_input == "r": # retry
                        break
    except IPAddressResolutionError as ip_exc:
        logging.error(f"Failed to resolve VM IP address: {ip_exc}")


if __name__ == "__main__":
    main()
