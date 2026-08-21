"""Legacy aggregator kept for compatibility; orchestrator builds structured responses."""


def aggregate_responses(agent_outputs):
    final_answer = []
    for output in agent_outputs:
        agent = output.get("agent", "agent")
        if "recommendation" in output:
            final_answer.append(f"[{agent}] {output['recommendation']}")
            continue
        final_answer.append(f"🔹 {agent.capitalize()} Suggestions:")
        for item in output.get("response", []):
            final_answer.append(f"- {item}")
        final_answer.append("")
    return "\n".join(final_answer)
