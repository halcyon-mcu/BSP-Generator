from dotenv import load_dotenv

_ = load_dotenv()

from app.prompt import EmbeddingsModel
from app.config import VERBOSITY

import asyncio
import logging

from langchain_text_splitters.character import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PDFPlumberLoader

from .retrieval.gpio import find_gpio_info


async def main():
    # Suppress pdfplumber warnings: https://github.com/jsvine/pdfplumber/discussions/529
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    # todo: replace with our own pdfplumber loader which
    # needs to support tabular data.
    loader = PDFPlumberLoader("./Specsheet.pdf")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    vector_store = Chroma.from_documents(chunks, EmbeddingsModel.TITAN_V2.get_client())

    gpio_info = await find_gpio_info(vector_store)
    # if not gpio_info:
    #     print("Failed to locate GPIO information in the PDF.")
    #     return

    # board_info = {
    #     "name": "MyBoard",
    #     "description": "A custom board for my project",
    #     "gpio": {
    #         "mmio_start": hex(gpio_info.start_address),
    #         "mmio_end": hex(gpio_info.end_address),
    #     },
    # }

    # desired_api = {
    #     "gpio": {
    #         "init": "void gpio_init(void);",
    #         "read": "uint32_t gpio_read(uint32_t pin);",
    #         "write": "void gpio_write(uint32_t pin, uint32_t value);",
    #     }
    # }

    # prompt = textwrap.dedent("""
    #     You are a professional developer creating a BSP (Board Support Package) for a hardware company building for microcontrollers.
    #     Here's information about the board in YAML:

    #     ```yaml
    #     {}```

    #     Create C code for this BSP with the following api:

    #     ```yaml
    #     {}```

    #     Ensure the code is well-structured, commented, and adheres to best practices for embedded systems programming.
    #     Respond PURELY with the C code, no explanations, extra text, or backticks for a code block.
    # """).format(yaml.dump(board_info), yaml.dump(desired_api))

    # if VERBOSITY >= 2:
    #     print("Generated prompt:")
    #     print(prompt)

    # resp = await invoke_model(
    #     model=Model.HAIKU,
    #     max_tokens=512,
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": prompt,
    #         }
    #     ],
    # )

    # print("Response from model:", resp)


if __name__ == "__main__":
    asyncio.run(main())
