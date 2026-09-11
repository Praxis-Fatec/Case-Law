from fastapi import FastAPI

from app.api import health

TAGS = [
    {
        "name": "infrastructure",
        "description": "Operational endpoints. Not part of the product surface.",
    },
]

app = FastAPI(
    title="Case Law API",
    summary="Consolidation and analysis of judicial precedents.",
    description=(
        "Search decisions across Brazilian courts, inspect the reasoning and "
        "measure how a subject is being judged.\n\n"
        "Every result links back to the document on the court's official site: "
        "the source always prevails over any summary this API produces."
    ),
    version="0.1.0",
    openapi_tags=TAGS,
)

app.include_router(health.router)
