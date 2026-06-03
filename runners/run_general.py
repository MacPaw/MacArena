"""Script to run end-to-end evaluation on the benchmark.
Utils and basic architecture credit to https://github.com/web-arena-x/webarena/blob/main/run.py.
"""

import argparse
import datetime
import json
import logging
import os
import shutil
import sys

from tqdm import tqdm

import runners.lib_run_single as lib_run_single
from desktop_env.desktop_env import DesktopEnv
from mm_agents.agents import get_agent

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

#  Logger Configs {{{ #
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

file_handler = logging.FileHandler(
    os.path.join("logs", "normal-{:}.log".format(datetime_str)), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join("logs", "debug-{:}.log".format(datetime_str)), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join("logs", "sdebug-{:}.log".format(datetime_str)), encoding="utf-8"
)

file_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)
sdebug_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)
file_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)
sdebug_handler.setFormatter(formatter)

stdout_handler.addFilter(logging.Filter("desktopenv"))
sdebug_handler.addFilter(logging.Filter("desktopenv"))

logger.addHandler(file_handler)
logger.addHandler(debug_handler)
logger.addHandler(stdout_handler)
logger.addHandler(sdebug_handler)
#  }}} Logger Configs #

logger = logging.getLogger("desktopenv.experiment")


def config() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation on the benchmark"
    )

    # environment config
    parser.add_argument("--path_to_vm", type=str, default=None)
    parser.add_argument(
        "--headless", action="store_true", help="Run in headless machine"
    )
    parser.add_argument(
        "--provider_name", type=str, default="utm", help="Name of the provider"
    )
    parser.add_argument(
        "--action_space", type=str, default="pyautogui", help="Action type"
    )
    parser.add_argument(
        "--observation_type",
        choices=["screenshot", "a11y_tree", "screenshot_a11y_tree", "som"],
        default="screenshot",
        help="Observation type",
    )
    parser.add_argument("--screen_width", type=int, default=1920)
    parser.add_argument("--screen_height", type=int, default=1080)
    parser.add_argument("--sleep_after_execution", type=float, default=0.0)
    parser.add_argument("--max_steps", type=int, default=15)

    # agent config
    parser.add_argument("--max_trajectory_length", type=int, default=15)
    parser.add_argument(
        "--test_config_base_dir", type=str, default="evaluation_examples"
    )

    # lm config
    parser.add_argument("--model", type=str, default="uitars")
    parser.add_argument("--run_name", type=str, default="uitars_benchmark_run")
    parser.add_argument("--model_type", type=str, default="qwen25vl")
    parser.add_argument("--infer_mode", type=str, default="qwen25vl_normal")
    parser.add_argument("--prompt_style", type=str, default="qwen25vl_normal")
    parser.add_argument("--input_swap", action="store_true", help="Use copy and paste to type content")
    parser.add_argument("--language", type=str, default="English")
    parser.add_argument("--max_pixels", type=float, default=16384*28*28)
    parser.add_argument("--min_pixels", type=float, default=100*28*28)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--top_k", type=int, default=-1)
    parser.add_argument("--history_n", type=int, default=5)
    parser.add_argument("--callusr_tolerance", type=int, default=3)
    parser.add_argument("--max_tokens", type=int, default=500)
    parser.add_argument("--stop_token", type=str, default=None)

    # uitars specific config
    parser.add_argument("--base_url", type=str, default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api_key", type=str, default="empty")

    # example config
    parser.add_argument("--domain", type=str, default="all")
    parser.add_argument(
        "--test_all_meta_path", type=str, default="evaluation_examples/test_all.json"
    )

    # logging related
    parser.add_argument("--result_dir", type=str, default="./results")
    args = parser.parse_args()

    return args


def test(args: argparse.Namespace, test_all_meta: dict) -> None:
    scores = []
    max_steps = args.max_steps

    # log args
    logger.info("Args: %s", args)

    api_key = args.api_key
    if api_key == "empty" and os.getenv("API_KEY"):
        api_key = os.getenv("API_KEY")

    args.api_key = api_key

    with DesktopEnv(
        path_to_vm=args.path_to_vm,
        action_space=args.action_space,
        headless=args.headless,
        require_a11y_tree=args.observation_type in ["a11y_tree", "screenshot_a11y_tree", "som"],
        provider_name=args.provider_name
    ) as env:
        agent = get_agent(args.model, args, env)

        for domain in tqdm(test_all_meta, desc="Domain"):
            for example_id in tqdm(test_all_meta[domain], desc="Example", leave=False):
                config_file = os.path.join(
                    args.test_config_base_dir, f"{domain}/{example_id}.json"
                )
                with open(config_file, "r", encoding="utf-8") as f:
                    example = json.load(f)

                logger.info(f"[Domain]: {domain}")
                logger.info(f"[Example ID]: {example_id}")

                instruction = example["instruction"]
                logger.info(f"[Instruction]: {instruction}")

                example_result_dir = os.path.join(
                    args.result_dir,
                    args.action_space,
                    args.observation_type,
                    args.run_name,
                    domain,
                    example_id,
                )
                os.makedirs(example_result_dir, exist_ok=True)

                # example start running
                try:
                    lib_run_single.run_single_example_n_times(
                        agent,
                        env,
                        example,
                        max_steps,
                        instruction,
                        args,
                        example_result_dir,
                        scores,
                        n_runs=2,
                    )
                except Exception as e:
                    logger.error(f"Exception in {domain}/{example_id}: {e}")
                    env.controller.end_recording(
                        os.path.join(example_result_dir, "recording.mp4")
                    )
                    with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                        f.write(
                            json.dumps(
                                {"Error": f"Time limit exceeded in {domain}/{example_id}"}
                            )
                        )
                        f.write("\n")

    logger.info(f"Average score: {(sum(scores) / len(scores) if scores else 0.0)*100} %")


def get_unfinished(
    action_space, run_name, observation_type, result_dir, total_file_json
):
    target_dir = os.path.join(result_dir, action_space, observation_type, run_name)

    if not os.path.exists(target_dir):
        return total_file_json
    
    finished = {}
    for domain in total_file_json.keys():
        domain_path = os.path.join(target_dir, domain)
        if not os.path.exists(domain_path):
            continue
    
        finished[domain] = []

        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                if example_id == "onboard":
                    continue

                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" not in os.listdir(example_path):
                        # empty all files under example_id
                        for file in os.listdir(example_path):
                            full_path = os.path.join(example_path, file)
                            if os.path.isfile(full_path):
                                os.remove(full_path)
                            elif os.path.isdir(full_path):
                                shutil.rmtree(full_path)
                    else:
                        finished[domain].append(example_id)

    if not finished:
        return total_file_json
    
    for domain, examples in finished.items():
        if domain in total_file_json:
            total_file_json[domain] = [
                x for x in total_file_json[domain] if x not in examples
            ]

    return total_file_json


def get_result(action_space, run_name, observation_type, result_dir, total_file_json):
    target_dir = os.path.join(result_dir, action_space, observation_type, run_name)
    if not os.path.exists(target_dir):
        print("New experiment, no result yet.")
        return None

    all_result = []

    for domain in total_file_json.keys():
        domain_path = os.path.join(target_dir, domain)
        if not os.path.exists(domain_path):
            continue

        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" in os.listdir(example_path):
                        # empty all files under example_id
                        try:
                            all_result.append(
                                float(
                                    open(
                                        os.path.join(example_path, "result.txt"), "r"
                                    ).read()
                                )
                            )
                        except:
                            all_result.append(0.0)

    if not all_result:
        print("New experiment, no result yet.")
        return None
    else:
        print("Current Success Rate:", sum(all_result) / len(all_result) * 100, "%")
        return all_result


if __name__ == "__main__":
    ####### The complete version of the list of examples #######
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    args = config()

    with open(args.test_all_meta_path, "r", encoding="utf-8") as f:
        test_all_meta = json.load(f)

    if args.domain != "all":
        test_all_meta = {args.domain: test_all_meta[args.domain]}

    test_file_list = get_unfinished(
        args.action_space,
        args.run_name,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )

    left_info = ""
    for domain in test_file_list:
        left_info += f"{domain}: {len(test_file_list[domain])}\n"
    logger.info(f"Left tasks:\n{left_info}")

    get_result(
        args.action_space,
        args.run_name,
        args.observation_type,
        args.result_dir,
        test_all_meta,
    )
    test(args, test_file_list)
