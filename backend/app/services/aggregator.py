def aggregate_responses(agent_outputs):
    final_answer = []

    for output in agent_outputs:
        final_answer.append(f"🔹 {output['agent'].capitalize()} Suggestions:")

        for item in output["response"]:
            final_answer.append(f"- {item}")

        final_answer.append("")  # spacing

    return "\n".join(final_answer)