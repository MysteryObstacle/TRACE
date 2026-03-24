from tools.knowledge.list_topics import list_topics
from tools.knowledge.read_doc import read_doc
from tools.knowledge.search import search


def build_tool_registry() -> dict[str, object]:
    return {
        'list_topics': list_topics,
        'read_doc': read_doc,
        'search': search,
    }
