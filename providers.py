"""
Execution layer.

Sends requests to providers, measures latency,
tracks token usage and calculates real cost.
"""


import time


from models import MODELS, estimate_cost, estimate_tokens



class QuotaError(RuntimeError):
    pass



class ProviderError(RuntimeError):
    pass



QUOTA_MARKERS = (
    "429",
    "quota",
    "resource_exhausted",
    "rate limit"
)



_GEMINI_CLIENTS = {}

_GROQ_CLIENTS = {}



def _is_quota(error):

    text = str(error).lower()

    return any(
        x in text
        for x in QUOTA_MARKERS
    )



def _gemini_client(api_key):

    from google import genai


    if api_key not in _GEMINI_CLIENTS:

        _GEMINI_CLIENTS[api_key] = (
            genai.Client(
                api_key=api_key
            )
        )


    return _GEMINI_CLIENTS[api_key]



def _groq_client(api_key):

    from groq import Groq


    if api_key not in _GROQ_CLIENTS:

        _GROQ_CLIENTS[api_key] = (
            Groq(
                api_key=api_key
            )
        )


    return _GROQ_CLIENTS[api_key]




def call_model(model_key, prompt, keys):


    spec = MODELS[model_key]


    provider = spec["provider"]


    api_key = keys.get(provider)


    if not api_key:

        raise ProviderError(
            f"{provider} API key missing"
        )



    start = time.perf_counter()



    try:


        if provider == "gemini":


            response = (
                _gemini_client(api_key)
                .models
                .generate_content(
                    model=spec["model"],
                    contents=prompt
                )
            )


            text = response.text or ""


            usage = getattr(
                response,
                "usage_metadata",
                None
            )


            input_tokens = getattr(
                usage,
                "prompt_token_count",
                None
            )


            output_tokens = getattr(
                usage,
                "candidates_token_count",
                None
            )




        elif provider == "groq":


            response = (
                _groq_client(api_key)
                .chat
                .completions
                .create(
                    model=spec["model"],
                    messages=[
                        {
                            "role":"user",
                            "content":prompt
                        }
                    ]
                )
            )


            text = (
                response
                .choices[0]
                .message
                .content
            )


            usage = getattr(
                response,
                "usage",
                None
            )


            input_tokens = getattr(
                usage,
                "prompt_tokens",
                None
            )


            output_tokens = getattr(
                usage,
                "completion_tokens",
                None
            )


        else:

            raise ProviderError(
                "Unknown provider"
            )



    except Exception as error:


        print(
            "\n===== PROVIDER ERROR ====="
        )

        print(
            "Model:",
            model_key
        )

        print(
            "Provider:",
            provider
        )

        print(
            repr(error)
        )

        print(
            "==========================\n"
        )



        if _is_quota(error):

            raise QuotaError(
                f"{model_key}: quota exhausted"
            )


        raise ProviderError(
            f"{model_key}: {error}"
        )



    latency = time.perf_counter()-start



    input_tokens = (
        input_tokens
        or estimate_tokens(prompt)
    )


    output_tokens = (
        output_tokens
        or estimate_tokens(text)
    )



    return {

        "model_key":model_key,

        "model":spec["model"],

        "provider":provider,

        "answer":text.strip(),

        "latency":round(latency,2),

        "input_tokens":input_tokens,

        "output_tokens":output_tokens,

        "cost":round(
            estimate_cost(
                model_key,
                input_tokens,
                output_tokens
            ),
            6
        ),

        "tokens_estimated":usage is None

    }





def call_with_fallback(
    model_key,
    prompt,
    keys,
    unavailable,
    order
):


    tried=[]


    candidates=[
        model_key
    ] + [
        x for x in order
        if x != model_key
    ]



    for candidate in candidates:


        if candidate in unavailable:

            continue



        try:

            result = call_model(
                candidate,
                prompt,
                keys
            )


            result["tried"]=tried

            result["fell_back"]=(
                candidate != model_key
            )


            return result



        except QuotaError as error:


            unavailable.add(candidate)

            tried.append(
                str(error)
            )



        except ProviderError as error:


            tried.append(
                str(error)
            )



    raise ProviderError(
        "Every model failed:\n"
        +
        "\n".join(tried)
    )