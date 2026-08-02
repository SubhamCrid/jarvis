"""
Declarative pipeline stages (SearchStage, FetchStage, ExtractStage, VerifyStage, RankStage, FormatStage).
"""

import logging
from typing import List, Optional
from jarvis.internet.budget import ExecutionBudget
from jarvis.internet.interfaces.search import SearchProvider
from jarvis.internet.pipeline.context import ContextExecutionState, ExecutionContext
from jarvis.internet.pipeline.stage import PipelineStage
from jarvis.internet.providers.registry import ProviderRegistry
from jarvis.internet.schemas import Citation, InternetDocument

logger = logging.getLogger("jarvis.internet.pipeline.stages")


class SearchStage(PipelineStage):
    name = "search"

    def __init__(self, registry: ProviderRegistry, provider_name: str = "duckduckgo", max_results: int = 5) -> None:
        self.registry = registry
        self.provider_name = provider_name
        self.max_results = max_results

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        context.state = ContextExecutionState.SEARCHING
        provider = self.registry.get_available_provider("search", self.provider_name)
        hits = await provider.search(
            query=context.query,
            max_results=self.max_results,
            cancellation_token=context.cancellation_token,
        )
        context.search_hits = hits
        return context


class FetchStage(PipelineStage):
    name = "fetch"

    def __init__(self, registry: ProviderRegistry, provider_name: str = "httpx") -> None:
        self.registry = registry
        self.provider_name = provider_name

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        context.state = ContextExecutionState.FETCHING
        provider = self.registry.get_available_provider("fetch", self.provider_name)
        fetched_pages = []

        for hit in context.search_hits[:budget.max_requests]:
            if context.cancellation_token and context.cancellation_token.is_cancelled():
                break
            try:
                page = await provider.fetch(
                    url=hit.url,
                    timeout_sec=budget.timeout_sec,
                    cancellation_token=context.cancellation_token,
                )
                await budget.consume_bytes(len(page.raw_content.encode("utf-8")))
                fetched_pages.append(page)
            except Exception as e:
                logger.warning(f"FetchStage error for '{hit.url}': {e}")

        context.fetched_pages = fetched_pages
        return context


class ExtractStage(PipelineStage):
    name = "extract"

    def __init__(self, registry: ProviderRegistry, provider_name: str = "trafilatura") -> None:
        self.registry = registry
        self.provider_name = provider_name

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        context.state = ContextExecutionState.EXTRACTING
        provider = self.registry.get_available_provider("extraction", self.provider_name)
        extracted_docs = []

        for page in context.fetched_pages:
            try:
                doc = await provider.extract(page, max_tokens=budget.max_tokens)
                await budget.consume_tokens(doc.token_count)
                extracted_docs.append(doc)
            except Exception as e:
                logger.warning(f"ExtractStage error for '{page.url}': {e}")

        context.extracted_documents = extracted_docs
        return context


class VerifyStage(PipelineStage):
    name = "verify"

    def __init__(self, registry: ProviderRegistry, provider_name: str = "cross_source") -> None:
        self.registry = registry
        self.provider_name = provider_name

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        context.state = ContextExecutionState.VERIFYING
        provider = self.registry.get_available_provider("verification", self.provider_name)
        verif = await provider.verify(context.extracted_documents, context.query)
        context.verification_result = verif
        return context


class RankStage(PipelineStage):
    name = "rank"

    def __init__(self, registry: ProviderRegistry, provider_name: str = "bm25") -> None:
        self.registry = registry
        self.provider_name = provider_name

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        context.state = ContextExecutionState.RANKING
        if context.search_hits:
            provider = self.registry.get_available_provider("ranking", self.provider_name)
            context.search_hits = await provider.rank(context.search_hits, context.query)
        return context


class FormatStage(PipelineStage):
    name = "format"

    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        docs: List[InternetDocument] = []

        for ext_doc in context.extracted_documents:
            citations = [
                Citation(
                    source_url=ext_doc.url,
                    title=ext_doc.title,
                    snippet=ext_doc.clean_markdown[:150],
                )
            ]
            doc = InternetDocument(
                url=ext_doc.url,
                title=ext_doc.title,
                content=ext_doc.clean_markdown,
                summary=ext_doc.clean_markdown[:300] + "...",
                citations=citations,
            )
            docs.append(doc)

        context.final_documents = docs
        context.state = ContextExecutionState.COMPLETED
        return context
