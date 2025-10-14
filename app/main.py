from dotenv import load_dotenv

_ = load_dotenv()

import pdfplumber
import asyncio
import yaml
import logging

from .retrieval.gpio import find_gpio_info
from .prompt import invoke_model, Model


async def main():
    # Suppress pdfplumber warnings: https://github.com/jsvine/pdfplumber/discussions/529
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    with pdfplumber.open("./Specsheet.pdf") as pdf:
        gpio_info = await find_gpio_info(pdf)
        if not gpio_info:
            print("GIO not found in the PDF.")
            return

        board_info = {
            "name": "MyBoard",
            "description": "A custom board for my project",
            "gpio": {
                "mmio_start": hex(gpio_info.start_address),
                "mmio_end": hex(gpio_info.end_address),
            },
        }

        desired_api = {
            "gpio": {
                "init": "void gpio_init(void);",
                "read": "uint32_t gpio_read(uint32_t pin);",
                "write": "void gpio_write(uint32_t pin, uint32_t value);",
            }
        }

        print("Generating BSP code...")

        resp = await invoke_model(
            model=Model.HAIKU,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": f"You are a professional developer creating a BSP (Board Support Package) for a hardware company building for microcontrollers. Here's information about the board in YAML:\n\n```{yaml.dump(board_info)}```\n. Create C code for this BSP with the following api:\n```{yaml.dump(desired_api)}```\n.",
                }
            ],
        )

        print("Response from model:", resp)


if __name__ == "__main__":
    asyncio.run(main())
