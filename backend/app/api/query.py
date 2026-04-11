from fastapi import APIRouter
from pydantic import BaseModel
from app.orchestrator.orchestrator import handle_query

router = APIRouter()


class QueryRequest(BaseModel):
  query: str

@router.post("/query")
def query_endpoint(request: QueryRequest):
  result = handle_query(request.query)
  return result