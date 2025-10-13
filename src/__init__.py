import pdfplumber
import os
from dotenv import load_dotenv
from anthropic import AnthropicBedrock
import boto3

bedrock = boto3.client("bedrock", region_name="us-east-1")
response = bedrock.list_foundation_models()

# Filter for Claude models
for model in response["modelSummaries"]:
    if "claude" in model["modelId"].lower():
        print(model["modelId"])

load_dotenv()

aws_access_key = os.getenv("AWS_ACCESS_KEY")
if not aws_access_key:
    raise ValueError("AWS_ACCESS_KEY not found in environment variables")

aws_secret_key = os.getenv("AWS_SECRET_KEY")
if not aws_secret_key:
    raise ValueError("AWS_SECRET_KEY not found in environment variables")

client = AnthropicBedrock(aws_access_key=aws_access_key, aws_secret_key=aws_secret_key)


def find_gio() -> tuple[int, int] | None:
    with pdfplumber.open("./Specsheet.pdf") as pdf:
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

                            return (start_addr, end_addr)


def main():
    gio_info = find_gio()
    if gio_info:
        print("Found GIO info. Making a basic bsp")

        # message = client.messages.create(
        #     model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        #     max_tokens=512,
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": f"You are a professional developer creating a BSP (Board Support Package) for a hardware company building for microcontrollers. The GIO (General Input/Output) address range starts at 0x{gio_info[0]:X} and ends at 0x{gio_info[1]:X}. Please help create the basic structure for this BSP.",
        #         }
        #     ],
        # )

        # print("Response from model:", message)
    else:
        print("GIO not found in the PDF.")


if __name__ == "__main__":
    main()
