from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator, FilterCondition

from ingest import load_index


def retrieve(query: str, top_k: int = 8, block: str = None, source_type: str = None, language: str = None) -> list:
    """
    Retrieve relevant chunks from the shared index.

    Args:
        query: The question or topic to search for.
        top_k: Number of chunks to return.
        block: Optional block filter (e.g. "GI", "cardio").
        source_type: Optional source type filter (e.g. "textbook", "lecture").
        language: Optional language filter ("EN" or "FR").

    Returns:
        List of NodeWithScore objects. Access .node.text and .node.metadata on each.
    """
    index = load_index()

    filters = _build_filters(block=block, source_type=source_type, language=language)

    retriever = index.as_retriever(
        similarity_top_k=top_k,
        filters=filters,
    )

    return retriever.retrieve(query)


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
