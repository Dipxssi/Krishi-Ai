def route_query(query: str):
    query = query.lower()
    agents = []


    # Finance
    if any(word in query for word in ["money", "loan", "finance", "cost"]):
        agents.append("finance")

    # Equipment
    if any(word in query for word in ["tractor", "equipment", "machine", "tools"]):
        agents.append("equipment")

    # Crop
    if any(word in query for word in ["crop", "leaf", "disease", "plant", "soil"]):
        agents.append("crop")

    # Market (more strict)
    if any(word in query for word in ["sell", "price", "market", "mandi"]):
        agents.append("market")

    return agents