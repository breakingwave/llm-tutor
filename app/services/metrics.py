from prometheus_client import Counter, Histogram

llm_calls = Counter(
    "llm_api_calls_total",
    "Total LLM / external API calls",
    ["module", "operation", "service", "model", "error"],
)
llm_tokens = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    ["module", "operation", "service", "model", "direction"],
)
llm_cost = Counter(
    "llm_cost_usd_total",
    "Estimated LLM cost in USD",
    ["module", "operation", "service", "model"],
)
llm_duration = Histogram(
    "llm_call_duration_seconds",
    "LLM / external API call latency",
    ["module", "operation", "service"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 30],
)
