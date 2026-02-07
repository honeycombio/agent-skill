"""Canonical constants for Honeycomb MCP plugin testing.

Single source of truth for valid tool names, calculation ops, filter ops,
and plugin structure expectations. Derived from the actual MCP server tool
definitions.
"""

# All 16 Honeycomb MCP tools
VALID_MCP_TOOLS = frozenset({
    "get_workspace_context", "get_environment", "get_dataset", "get_dataset_columns",
    "find_columns", "find_queries",
    "run_query", "get_query_results", "run_bubbleup",
    "get_trace", "get_service_map",
    "get_slos", "get_triggers",
    "create_board", "list_boards",
    "feedback",
})

# Ops that REQUIRE a column
OPS_REQUIRING_COLUMN = frozenset({
    "SUM", "AVG", "COUNT_DISTINCT", "MAX", "MIN",
    "P001", "P01", "P05", "P10", "P20", "P25", "P50", "P75", "P80", "P90", "P95", "P99", "P999",
    "HEATMAP", "RATE_SUM", "RATE_AVG", "RATE_MAX",
})

# Ops that MUST NOT have a column
OPS_FORBIDDING_COLUMN = frozenset({"CONCURRENCY"})

# The 5 required skill directories
REQUIRED_SKILLS = [
    "query-patterns",
    "production-investigation",
    "slos-and-triggers",
    "otel-instrumentation",
    "beeline-migration",
]

# MCP tool categories for cross-referencing
TOOL_CATEGORIES = {
    "context": {"get_workspace_context", "get_environment", "get_dataset", "get_dataset_columns"},
    "discovery": {"find_columns", "find_queries"},
    "query": {"run_query", "get_query_results", "run_bubbleup"},
    "trace": {"get_trace", "get_service_map"},
    "reliability": {"get_slos", "get_triggers"},
    "boards": {"create_board", "list_boards"},
    "meta": {"feedback"},
}
