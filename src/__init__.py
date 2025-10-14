from dotenv import load_dotenv
import boto3, json, os, pdfplumber, asyncio

load_dotenv()

aws_access_key = os.getenv("AWS_ACCESS_KEY")
if not aws_access_key:
    raise ValueError("AWS_ACCESS_KEY not found in environment variables")

aws_secret_key = os.getenv("AWS_SECRET_KEY")
if not aws_secret_key:
    raise ValueError("AWS_SECRET_KEY not found in environment variables")

client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-2",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
)


# This function is left Asynchronous as it may in the future make use of LLMs for finding information.
async def find_gio() -> tuple[int, int] | None:
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


async def main():
    gio_info = await find_gio()
    if gio_info:
        print("Found GIO info. Making a basic bsp")

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [
                {
                    "role": "user",
                    "content": f"You are a professional developer creating a BSP (Board Support Package) for a hardware company building for microcontrollers. The GIO (General Input/Output) address range starts at 0x{gio_info[0]:X} and ends at 0x{gio_info[1]:X}. Please help create the basic structure for this BSP.",
                }
            ],
        }

        resp = client.invoke_model(
            modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            body=json.dumps(body),
        )

        response_body = json.loads(resp["body"].read())
        print("Response from model:", response_body["content"][0]["text"])
    else:
        print("GIO not found in the PDF.")


if __name__ == "__main__":
    asyncio.run(main())
