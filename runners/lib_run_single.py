import datetime
import json
import logging
import os
import time
from pathlib import Path
from wrapt_timeout_decorator import *
import subprocess

logger = logging.getLogger("desktopenv.experiment")


CLOSE_ALL_APPS_COMMAND = """
osascript -e '
tell application "System Events"
    set quitapps to name of every application process whose visible is true and name is not "Finder"
    repeat with closeall in quitapps
        try
            do shell script "killall -9 " & quoted form of closeall
        end try
    end repeat
end tell
'
"""


def run_single_example(agent, env, example, max_steps, instruction, args, example_result_dir, scores, reset_env = True):
    runtime_logger = setup_logger(example, example_result_dir)

    agent.reset(runtime_logger)

    if reset_env:
        env.reset(task_config=example)

    time.sleep(10) # Wait for the environment to be ready

    obs = env._get_obs() # Get the initial observation
    done = False
    step_idx = 0

    # start experiment
    env.controller.start_recording()
    while not done and step_idx < max_steps:
        response, actions = agent.predict(instruction, obs)

        for action in actions:
            # Capture the timestamp before executing the action
            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            logger.info("Step %d: %s", step_idx + 1, action)
            obs, reward, done, info = env.step(action, args.sleep_after_execution)

            logger.info("Reward: %.2f", reward)
            logger.info("Done: %s", done)

            # Save screenshot and trajectory information
            with open(os.path.join(example_result_dir, f"step_{step_idx + 1}_{action_timestamp}.png"), "wb") as _f:
                _f.write(obs['screenshot'])

            with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                f.write(
                    json.dumps({
                        "step_num": step_idx + 1,
                        "action_timestamp": action_timestamp,
                        "action": action,
                        "reward": reward,
                        "done": done,
                        "info": info,
                        "screenshot_file": f"step_{step_idx + 1}_{action_timestamp}.png"
                    })
                )
                f.write("\n")

            if done:
                logger.info("The episode is done.")
                break

        step_idx += 1
    
    # save the final result
    result = env.evaluate()
    logger.info("Result: %.2f", result)
    scores.append(result)
    with open(os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8") as f:
        f.write(f"{result}\n")

    # write history
    with open(os.path.join(example_result_dir, "history_responses.txt"), "w", encoding="utf-8") as f:
        for i, resp in enumerate(agent.history_responses):
            f.write(f"Turn {i + 1}\n")
            f.write(f"Response:\n{resp}\n")
            f.write("\n")

    # save video
    env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))


def run_single_example_n_times(agent, env, example, max_steps, instruction, args, example_result_dir, scores, n_runs=2):
    scores_tmp = []

    # First run with environment reset
    example_result_dir_tmp = Path(example_result_dir) / "run_1"
    example_result_dir_tmp.mkdir(parents=True, exist_ok=True)
    run_single_example(agent, env, example, max_steps, instruction, args, example_result_dir_tmp, scores_tmp, reset_env=True)

    try:
        result = scores_tmp[-1][0] if isinstance(scores_tmp[-1], tuple) else scores_tmp[-1]
    except IndexError:
        result = 0.0

    for i in range(2, n_runs + 1):
        env.controller.run_bash_script(CLOSE_ALL_APPS_COMMAND)

        example_result_dir_tmp = Path(example_result_dir) / f"run_{i}"
        example_result_dir_tmp.mkdir(parents=True, exist_ok=True)
        run_single_example(agent, env, example, max_steps, instruction, args, example_result_dir_tmp, scores_tmp, reset_env=False)

        try:
            result_tmp = scores_tmp[-1][0] if isinstance(scores_tmp[-1], tuple) else scores_tmp[-1]
            result = max(result_tmp, result)
        except IndexError:
            pass

    scores.append(result)

    with open(os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8") as f:
        f.write(f"{result}\n")

def setup_logger(example, example_result_dir):
    runtime_logger = logging.getLogger(f"desktopenv.example.{example['id']}")
    runtime_logger.setLevel(logging.DEBUG)
    runtime_logger.addHandler(logging.FileHandler(os.path.join(example_result_dir, "runtime.log")))
    return runtime_logger
