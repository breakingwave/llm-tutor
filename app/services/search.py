import time
import logging
from tavily import TavilyClient

from app.config import GatheringSettings
from app.models.api_log import APICallLog
from app.services.api_logger import APILogger

logger = logging.getLogger("llm_tutor.search")


class SearchService:
    def __init__(
        self,
        api_key: str,
        settings: GatheringSettings,
        api_logger: APILogger,
    ):
        self.client = TavilyClient(api_key=api_key) if api_key else None
        self.settings = settings
        self.api_logger = api_logger

    async def search(
        self,
        query: str,
        max_results: int = 5,
        session_id: str | None = None,
    ) -> list[dict]:
        if not self.client:
            logger.warning("Tavily client not configured (no API key)")
            return []

        start = time.perf_counter()
        error_str = None
        results = []

        try:
            response = self.client.search(
                query=query,
                search_depth=self.settings.tavily_search_depth,
                max_results=max_results,
            )
            results = response.get("results", [])
        except Exception as e:
            error_str = str(e)
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module="gathering",
                operation="web_search",
                service="tavily",
                latency_ms=latency,
                request_payload={"query": query, "max_results": max_results},
                response_payload={"num_results": len(results)},
                error=error_str,
                session_id=session_id,
            ))

        return results
