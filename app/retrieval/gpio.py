from pdfplumber.pdf import PDF
from dataclasses import dataclass


@dataclass
class GPIOInfo:
    start_address: int
    end_address: int


# This function is left Asynchronous as it may in the future make use of LLMs for finding information.
async def find_gpio_info(pdf: PDF) -> GPIOInfo | None:
    device_memory_map_found = False

    for page in pdf.pages:
        # Check if this page contains "Device Memory Map" header
        page_text = page.extract_text()
        if page_text and "Device Memory Map" in page_text:
            device_memory_map_found = True

        if device_memory_map_found or "Device Memory Map" in (page_text or ""):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row[0] and row[0].strip().startswith("GIO"):
                        start_addr_str = str(row[2]).strip().replace("_", "")
                        end_addr_str = str(row[3]).strip().replace("_", "")

                        start_addr = int(start_addr_str, 16)
                        end_addr = int(end_addr_str, 16)

                        return GPIOInfo(start_address=start_addr, end_address=end_addr)
