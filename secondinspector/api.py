import json
import os

from openai import AsyncOpenAI, OpenAI

SPARK = "muse-spark-1.3"
WONDER = "muse-wonder-1.0"


def base_url():
    return os.environ.get("base_url", "https://api.meta.ai/v1")


def sync_client():
    return OpenAI(base_url=base_url(), api_key=os.environ["MODEL_API_KEY"])


def async_client():
    return AsyncOpenAI(base_url=base_url(), api_key=os.environ["MODEL_API_KEY"])


def spark_json(client, content, schema, name, *, model=SPARK):
    """Request structured output, using Spark unless a different model is specified."""
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
    )
    if response.status != "completed":
        raise RuntimeError(f"{model} returned {response.status} for {name}")
    return json.loads(response.output_text)
