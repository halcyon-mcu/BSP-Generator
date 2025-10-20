from langchain_community.vectorstores import Chroma
from dataclasses import dataclass

from app.util import documents_to_yaml
from app.prompt import invoke_model, Model


@dataclass
class GPIOInfo:
    start_address: int
    end_address: int


async def find_gpio_info(vector_store: Chroma) -> GPIOInfo | None:
    similar_info = vector_store.similarity_search_with_score(
        "GPIO, GIO, General Purpose Input Output, memory map, address range, GIOA",
        k=50,
    )

    # Filter out entries with score < 0.7
    similar_info = [doc for doc, score in similar_info if score > 0.7]
    if len(similar_info) == 0:
        return None

    yaml_input = documents_to_yaml(similar_info)

    output = await invoke_model(
        Model.HAIKU_4_5,
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""
You are given the following YAML data extracted from a technical specification document:
```yaml
{yaml_input}
```

Extract the GPIO memory map start and end addresses from the data.
Provide the result in the following JSON format.
```json
{{"start_address": "0x...", "end_address": "0x...", "stride": int, "pin_count": int, "gpio_typedef": StructField[]}}
```
Where StructField is defined as:
```json
{{"name": "field_name", "type": "uint32_t | uint64_t | uint8_t | uint16_t", "description": "field_description"}}
```
Purely respond with the JSON, no explanations or extra text. Do not respond with backticks for code blocks.
        """,
            }
        ],
    )

    print("GPIO extraction output:", output)

    return None
