from agentfw.runtime.factory import build_default_engine


def main() -> None:
    engine, _ = build_default_engine()

    state = engine.run_to_completion(
        agent_name="task_complexity_classifier",
        input_json={"task_text": "Зроби план складного проєкту з агентами і гілками."},
    )

    print(state.vars.get("task_text"))
    print(state.vars.get("needs_planning"))


if __name__ == "__main__":
    main()
