from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from app.db.session import save_tool_trace
from app.schemas.models import ToolTrace


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[Callable, type[BaseModel]]] = {}
        self.traces: list[ToolTrace] = []
        self.farmer_id: str | None = None

    def register(self, name: str, fn: Callable, args_model: type[BaseModel]) -> None:
        self._tools[name] = (fn, args_model)

    def reset(self, farmer_id: str | None = None) -> None:
        self.traces = []
        self.farmer_id = farmer_id

    def execute(
        self,
        *,
        agent: str,
        tool: str,
        arguments: dict[str, Any],
        repair_fn: Callable[[dict[str, Any], str], dict[str, Any] | None] | None = None,
    ) -> ToolTrace:
        if tool not in self._tools:
            trace = ToolTrace(
                agent=agent,
                tool=tool,
                arguments=arguments,
                status="error",
                error=f"Unknown tool: {tool}",
            )
            self._record(trace)
            return trace

        fn, args_model = self._tools[tool]
        try:
            validated = args_model.model_validate(arguments)
        except ValidationError as exc:
            repaired = repair_fn(arguments, str(exc)) if repair_fn else None
            if repaired is None:
                trace = ToolTrace(
                    agent=agent,
                    tool=tool,
                    arguments=arguments,
                    status="invalid_args",
                    error=str(exc),
                )
                self._record(trace)
                return trace
            try:
                validated = args_model.model_validate(repaired)
                arguments = repaired
            except ValidationError as exc2:
                trace = ToolTrace(
                    agent=agent,
                    tool=tool,
                    arguments=arguments,
                    status="invalid_args",
                    error=str(exc2),
                )
                self._record(trace)
                return trace

        try:
            output = fn(**validated.model_dump())
            trace = ToolTrace(
                agent=agent,
                tool=tool,
                arguments=validated.model_dump(),
                status="success",
                output=output if isinstance(output, (dict, list, str, int, float, bool)) or output is None else dict(output),
            )
        except Exception as exc:  # noqa: BLE001
            # One retry with repair if provided
            if repair_fn:
                repaired = repair_fn(arguments, str(exc))
                if repaired is not None:
                    try:
                        validated = args_model.model_validate(repaired)
                        output = fn(**validated.model_dump())
                        trace = ToolTrace(
                            agent=agent,
                            tool=tool,
                            arguments=validated.model_dump(),
                            status="success_after_retry",
                            output=output if isinstance(output, (dict, list, str, int, float, bool)) or output is None else dict(output),
                        )
                        self._record(trace)
                        return trace
                    except Exception as exc2:  # noqa: BLE001
                        trace = ToolTrace(
                            agent=agent,
                            tool=tool,
                            arguments=arguments,
                            status="error",
                            error=str(exc2),
                        )
                        self._record(trace)
                        return trace
            trace = ToolTrace(
                agent=agent,
                tool=tool,
                arguments=arguments,
                status="error",
                error=str(exc),
            )

        self._record(trace)
        return trace

    def _record(self, trace: ToolTrace) -> None:
        self.traces.append(trace)
        try:
            save_tool_trace(
                farmer_id=self.farmer_id,
                agent=trace.agent,
                tool=trace.tool,
                arguments=trace.arguments,
                status=trace.status,
                output=trace.output,
                error=trace.error,
                timestamp=trace.timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        except Exception:  # noqa: BLE001
            pass


# Shared request-scoped registry instance; orchestrator resets per query
tool_registry = ToolRegistry()
