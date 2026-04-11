from app.orchestrator.router import route_query
from app.agents.finance_agent import finance_agent
from app.agents.crop_agent import crop_agent
from app.agents.equipment_agent import equipment_agent
from app.agents.market_agent import market_agent
from app.services.aggregator import aggregate_responses


def handle_query(query: str):
    agents = route_query(query)
    responses = []

    if "finance" in agents:
        responses.append(finance_agent(query))

    if "crop" in agents:
        responses.append(crop_agent(query))

    if "equipment" in agents:
        responses.append(equipment_agent(query))

    if "market" in agents:
        responses.append(market_agent(query))

    final_answer = aggregate_responses(responses)

    return {
        "query": query,
        "final_answer": final_answer,
        "agents_used": agents
    }