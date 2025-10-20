import json
import os
import boto3
from langchain_aws import BedrockEmbeddings

from app.config import VERBOSITY

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

embeddings_titan_v2 = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0", client=client
)

from enum import Enum


class Model(Enum):
    HAIKU_3_0 = "haiku3.0"
    HAIKU_4_5 = "haiku4.5"
    SONNET_3_5 = "sonnet3.5"
    SONNET_4_5 = "sonnet4.5"

    def get_model_id(self):
        model_ids = {
            "haiku3.0": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "sonnet3.5": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "haiku4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        }

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


from enum import Enum


class EmbeddingsModel(Enum):
    TITAN_V2 = "titan-v2"

    def get_client(self) -> BedrockEmbeddings:
        model_clients = {"titan-v2": embeddings_titan_v2}
        return model_clients[self.value]


def get_embeddings_client(model: EmbeddingsModel) -> BedrockEmbeddings:
    return model.get_client()
