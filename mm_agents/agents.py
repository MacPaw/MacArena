from argparse import Namespace

def get_agent(agent_name: str, args: Namespace, env=None):
    agent_name = agent_name.lower()

    if "uitars" in agent_name or "ui-tars" in agent_name:
        from mm_agents.uitars_agent import UITARSAgent
        return UITARSAgent(
            action_space=args.action_space,
            observation_type=args.observation_type,
            max_trajectory_length=args.max_trajectory_length,
            model_type=args.model_type,
            model=args.model,
            vlm = {
                "base_url": args.base_url,
                "api_key": args.api_key,
            },
            runtime_conf = {
                "infer_mode": args.infer_mode,
                "prompt_style": args.prompt_style,
                "input_swap": args.input_swap,
                "language": args.language,
                "history_n": args.history_n,
                "max_pixels": args.max_pixels,
                "min_pixels": args.min_pixels,
                "callusr_tolerance": args.callusr_tolerance,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "max_tokens": args.max_tokens
            }
        )
    elif "gpt" in agent_name or "openai" in agent_name or "computer-use-preview" in agent_name:
        from mm_agents.openai_agent import OpenAICUAAgent
        return OpenAICUAAgent(
            env,
            platform="mac",
            action_space=args.action_space,
            observation_type=args.observation_type,
            max_trajectory_length=args.max_trajectory_length,
            max_tokens=args.max_tokens,
            client_password="admin",
            provider_name=args.provider_name,
            screen_width=args.screen_width,
            screen_height=args.screen_height
        )
    elif "qwen3" in agent_name:
        from mm_agents.qwen3_agent import Qwen3VLAgent
        return Qwen3VLAgent(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            max_tokens=args.max_tokens,
            action_space=args.action_space,
            observation_type=args.observation_type,
            history_n = args.history_n
        )

