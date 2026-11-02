import json
import os

from openai import AsyncOpenAI, OpenAI

SPARK = "muse-spark-1.3"


def base_url():
    return os.environ.get("base_url", "https://api.meta.ai/v1")


def sync_client():
    return OpenAI(base_url=base_url(), api_key=os.environ["MODEL_API_KEY"])


def async_client():
    return AsyncOpenAI(base_url=base_url(), api_key=os.environ["MODEL_API_KEY"])


def spark_search(client, prompt):
    """Ask Spark with web search on; return its answer and the URLs it cited first, then the ones it saw."""
    response = client.responses.create(
        model=SPARK,
        tools=[{"type": "web_search"}],
        include=["web_search_call.results"],
        input=prompt,
    )
    cited, seen = [], []
    for item in response.output:
        data = item.model_dump()
        seen += [result.get("url") for result in data.get("results") or []]
        for part in data.get("content") or []:
            cited += [note.get("url") for note in part.get("annotations") or []]
    return response.output_text, [url for url in dict.fromkeys(cited + seen) if url]


def spark_json(client, content, schema, name, model=SPARK):
    """Ask Spark for output matching a JSON schema and return the parsed object."""
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
    )
    if response.status != "completed":
        raise RuntimeError(f"Spark returned {response.status} for {name}")
    return json.loads(response.output_text)
