## Evaluation examples

Here we put the data examples to benchmark the ability of agents when interacting with GUI.
The `OSWorld` examples have the following structure:

```jsonc
{
  "id": "uuid",
  "snapshot": "snapshot_name", // not used in macOS implementation
  "instruction": "natural language instruction",
  "source": "source", // source of the task. maybe some link to the original task description or "own"
  "config": [{...}, {...}], // list of config steps to prepare the environment before running the trajectory
  "trajectory": "trajectories/", // path to the trajectory file. OSWorld promised to add it in the future.
  "related_apps": ["app1", "app2"], // list of related applications
  "evaluator": {
    "postconfig": [{...}, {...}], // list of config steps to prepare the environment before running the evaluation
    "func": "evaluator_function_name", // name of the evaluator function
    "result": {...}, // expected result for the evaluator function
    "expected": {...} // expected additional information for the evaluator function
  },
  "proxy": bool, // whether to use proxy (not used in this implementation)
  "fixed_ip": bool, // whether to use fixed IP (not used in this implementation)
  "possibility_of_env_change": "low/medium/high" // possibility of environment change during the task (not used in this implementation)
}
```
At the same time, `macosworld` examples have a slightly different structure:

```jsonc
{
  "id": "uuid",
  "snapshot": {...}, // snapshot configuration (not used in this implementation)
  "force_snapshot_recovery": false, // whether to force snapshot recovery (we always do it in this implementation)
  "pre_command": "command to run before the task", // command to prepare the environment before running the task
  "before_action_delay_seconds": int, // delay before starting the task
  "before_grading_delay_seconds": int, // delay before starting the evaluation
  "instruction": "natural language instruction",
  "source": "macosworld", // source of the task
  "evaluator": [[str, int], ...] // list of evaluators and their rewards.
}
