from langchain_community.vectorstores import Chroma
from dataclasses import dataclass


@dataclass
class GPIOInfo:
    start_address: int
    end_address: int


async def find_gpio_info(vector_store: Chroma) -> GPIOInfo | None:
    # Search for GPIO-related information in the vector store
    gpio_query = "GPIO memory map start address end address"
    results = vector_store.similarity_search(gpio_query, k=5)

    if not results:
        return None

    

    return None
