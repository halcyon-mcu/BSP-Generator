from langchain_core.documents import Document


def documents_to_yaml(docs: list[Document]) -> str:
    import yaml

    data = []
    for doc in docs:
        data.append({"content": doc.page_content, "metadata": doc.metadata})

    return yaml.dump(data, default_flow_style=False)
