import json
import os
import boto3

aws_access_key = os.getenv("AWS_ACCESS_KEY")
if not aws_access_key:
    raise ValueError("AWS_ACCESS_KEY not found in environment variables")

aws_secret_key = os.getenv("AWS_SECRET_KEY")
if not aws_secret_key:
    raise ValueError("AWS_SECRET_KEY not found in environment variables")

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-2",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
)

from enum import Enum


class Model(Enum):
    HAIKU = "haiku"

    def get_model_id(self):
        model_ids = {"haiku": "us.anthropic.claude-3-haiku-20240307-v1:0"}

        return model_ids[self.value]


from typing import TypedDict, Literal


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


async def invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> str:
    body = {
        "max_tokens": max_tokens,
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
    }

    response = client.invoke_model(modelId=model.get_model_id(), body=json.dumps(body))

    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]
