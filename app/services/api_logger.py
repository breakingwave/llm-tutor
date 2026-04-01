import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import LoggingSettings
from app.models.api_log import APICallLog

logger = logging.getLogger("llm_tutor.api_calls")


class APILogger:
    def __init__(self, settings: LoggingSettings):
        self.settings = settings
        self.log_dir = Path(settings.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"api_calls_{date_str}.jsonl"

    def log_call(self, log: APICallLog) -> None:
        payload = log.model_dump(mode="json")

        if not self.settings.log_full_payloads:
            for key in ("request_payload", "response_payload"):
                if key in payload and payload[key]:
                    payload[key] = _truncate_payload(payload[key])

        line = json.dumps(payload, default=str)

        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            f.write(line + "\n")

        level_str = "ERROR" if log.error else "DEBUG"
        logger.log(
            logging.getLevelName(level_str),
            "[%s/%s] %s model=%s latency=%.0fms tokens_in=%s tokens_out=%s cost=$%s%s",
            log.module,
            log.operation,
            log.service,
            log.model or "-",
            log.latency_ms,
            log.input_tokens or "-",
            log.output_tokens or "-",
            f"{log.cost_estimate_usd:.4f}" if log.cost_estimate_usd else "-",
            f" ERROR: {log.error}" if log.error else "",
        )

    def query_logs(
        self,
        module: str | None = None,
        service: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        results = []
        for log_file in sorted(self.log_dir.glob("api_calls_*.jsonl"), reverse=True):
            with open(log_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if module and entry.get("module") != module:
                        continue
                    if service and entry.get("service") != service:
                        continue
                    if since and entry.get("timestamp", "") < since.isoformat():
                        continue
                    if until and entry.get("timestamp", "") > until.isoformat():
                        continue
                    results.append(entry)
                    if len(results) >= limit:
                        return results
        return results

    def aggregate_costs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        group_by: tuple[str, ...] = ("module", "service"),
    ) -> list[dict]:
        grouped: dict[tuple, dict] = {}
        for entry in self.query_logs(since=since, until=until, limit=1_000_000):
            cost = float(entry.get("cost_estimate_usd") or 0.0)
            key = tuple(entry.get(field, "unknown") for field in group_by)
            if key not in grouped:
                grouped[key] = {
                    "group": {field: entry.get(field, "unknown") for field in group_by},
                    "calls": 0,
                    "total_cost_usd": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            grouped[key]["calls"] += 1
            grouped[key]["total_cost_usd"] += cost
            grouped[key]["input_tokens"] += int(entry.get("input_tokens") or 0)
            grouped[key]["output_tokens"] += int(entry.get("output_tokens") or 0)
        return sorted(grouped.values(), key=lambda row: row["total_cost_usd"], reverse=True)


def _truncate_payload(payload: dict, max_str_len: int = 200) -> dict:
    truncated = {}
    for k, v in payload.items():
        if isinstance(v, str) and len(v) > max_str_len:
            truncated[k] = v[:max_str_len] + "...[truncated]"
        elif isinstance(v, dict):
            truncated[k] = _truncate_payload(v, max_str_len)
        elif isinstance(v, list) and len(v) > 5:
            truncated[k] = v[:5] + [f"...+{len(v) - 5} more"]
        else:
            truncated[k] = v
    return truncated
