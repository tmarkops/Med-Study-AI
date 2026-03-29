from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator, FilterCondition
from sentence_transformers import CrossEncoder

from ingest import load_index

_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_RERANK_OVERSAMPLE = 3  # fetch this many × top_k before reranking
_reranker_instance = None


def _get_reranker() -> CrossEncoder:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoder(_RERANKER_MODEL)
    return _reranker_instance


def retrieve(query: str, top_k: int = 8, block: str = None, source_type: str = None, language: str = None, rerank: bool = True) -> list:
    """
    Retrieve relevant chunks from the shared index.

    Args:
        query: The question or topic to search for.
        top_k: Number of chunks to return.
        block: Optional block filter (e.g. "GI", "cardio").
        source_type: Optional source type filter (e.g. "textbook", "lecture").
        language: Optional language filter ("EN" or "FR").
        rerank: If True, oversample then rerank with a cross-encoder before returning top_k.

    Returns:
        List of NodeWithScore objects. Access .node.text and .node.metadata on each.
    """
    index = load_index()

    filters = _build_filters(block=block, source_type=source_type, language=language)

    fetch_k = top_k * _RERANK_OVERSAMPLE if rerank else top_k
    retriever = index.as_retriever(
        similarity_top_k=fetch_k,
        filters=filters,
    )

    nodes = retriever.retrieve(query)

    if rerank and len(nodes) > top_k:
        reranker = _get_reranker()
        pairs = [(query, node.node.text) for node in nodes]
        scores = reranker.predict(pairs)
        ranked = sorted(zip(scores, nodes), key=lambda x: x[0], reverse=True)
        nodes = [node for _, node in ranked[:top_k]]

    return nodes


def _build_filters(block=None, source_type=None, language=None) -> MetadataFilters | None:
    conditions = []

    if block and block != "general":
        conditions.append(MetadataFilter(key="block", value=block, operator=FilterOperator.EQ))
    if source_type:
        conditions.append(MetadataFilter(key="source_type", value=source_type, operator=FilterOperator.EQ))
    if language:
        conditions.append(MetadataFilter(key="language", value=language, operator=FilterOperator.EQ))

    if not conditions:
        return None

    return MetadataFilters(filters=conditions, condition=FilterCondition.AND)
