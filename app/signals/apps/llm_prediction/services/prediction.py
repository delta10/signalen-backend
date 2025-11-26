# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2025 Delta10 B.V.
from functools import lru_cache

from django.db.models import QuerySet, Q
from django.utils.text import slugify
from openai import OpenAI
import json

from signals import settings
from signals.apps.llm_prediction.models import LlmResponse
from signals.apps.signals.models import Category


_client = None

def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_URL
        )
    return _client


def get_categories_with_description() -> QuerySet[tuple[str, str, str]]:
    categories = (Category.objects
        .filter(parent__isnull=False)
        .filter(~Q(description=""), description__isnull=False)
        .values_list("parent__name", "name", "description")
    )

    return categories


def format_categories(categories: QuerySet[tuple[str, str, str]]) -> str:
    result = []
    for parent_name, name, description in categories:
        result.append(f"  - {parent_name} -> {name}: {description}")

    return "\n".join(result)


@lru_cache(maxsize=1)
def get_system_prompt() -> str:
    categories = get_categories_with_description()

    system_prompt = f"""
        You are a classification assistant. Your task is to assign the most appropriate subcategory from the hierarchy. 
        You may only choose a specific subcategory if the message clearly matches its description. 
        If the message fits a parent category but not a specific subcategory, choose that parent’s “Overig” subcategory.
        If the message does not match any parent category, choose:
        "main_category": "Overig"
        "sub_category": "Overig"
        
        ### Category Hierarchy
        {format_categories(categories)}
        
        ### Classification Rules
        1. Understand the message. Read the message carefully and infer its real-world meaning.
        2. Choose exactly one subcategory. Never return multiple or top-level categories.
        3. Base your choice strictly on meaning and the category descriptions. Do not rely only on keywords.
        4. Only choose a specific subcategory if the message clearly and directly matches that subcategory’s definition. 
           If the meaning does not strongly fit a specific subcategory, do NOT pick it.
        5. If multiple subcategories seem possible, choose the one with the most specific and direct semantic match.
        6. Never create, alter, or merge categories. Use only the categories exactly as listed.
        7. If a message clearly belongs to a parent category but does not strongly match any of that parent’s specific subcategories, then assign the subcategory “Overig” for that parent. The resulting subcategory label must use the pattern:
           "Overig <main_category>"
        8. If the message does not clearly match any parent category at all, return:
           "main_category": "Overig"
           "sub_category": "Overig"
        
        ### Output Format
        Return a single JSON object exactly like this:
        {{
          "main_category": "<main_category>",
          "sub_category": "<sub_category>",
          "text": "<original_message>"
        }}
        
        ### Example
        **Message:**
        A car has crashed into a tree.
        
        **Expected Output:**
        {{
          "main_category": "Openbaar groen en water"
          "sub_category": "Boom",
          "text": "A car has crashed into a tree."
        }}
        
        ### Message
        {{message}}
        """

    return system_prompt


def get_prediction(text: str) -> LlmResponse:
    prompt = get_system_prompt()

    client = get_openai_client()
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        model='mistral-small-3.2-24b-instruct-2506',
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "LlmResponse",
                "schema": LlmResponse.model_json_schema(),
            }
        },
        temperature=0.0,
        max_tokens=150,
    )

    output = json.loads(response.choices[0].message.content)

    return LlmResponse(**output)


def resolve_prediction(prediction: LlmResponse) -> tuple[str, str]:
    """
    prediction.main_category and prediction.sub_category are strings from the LLM.
    Returns actual Category slugs or fallback Overig/Overig.
    """
    main_slug = slugify(prediction.main_category or "")
    sub_slug = slugify(prediction.sub_category or "")

    main_cat = Category.objects.filter(parent__isnull=True, slug=main_slug).first()
    if not main_cat:
        return "overig", "overig"

    sub_cat = Category.objects.filter(parent=main_cat, slug=sub_slug).first()
    if not sub_cat:
        # Fallback to "Overig" child for this parent
        overig_sub = Category.objects.filter(parent=main_cat, slug=f"overig-{main_slug}").first()

        if overig_sub:
            return main_slug, overig_sub.slug

        return "overig", "overig"

    return main_slug, sub_slug
