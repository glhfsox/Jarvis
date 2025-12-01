from typing import List, Dict , cast, Sequence
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from config import load_settings


_settings = load_settings()
_client = OpenAI(api_key=_settings.openai_key)


def ask_llm(messages :  Sequence[ChatCompletionMessageParam]) -> str:
    response = _client.chat.completions.create(
        model=_settings.chat_model,
        messages=list(messages),
    )
    return response.choices[0].message.content or ""
