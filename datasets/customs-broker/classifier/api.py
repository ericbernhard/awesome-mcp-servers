#!/usr/bin/env python3
"""
HTTP API for the HTS + PGA classifier.

    pip install fastapi uvicorn anthropic
    export ANTHROPIC_API_KEY=...
    uvicorn api:app --reload

    curl -s localhost:8000/classify -H 'content-type: application/json' \
      -d '{"description":"men''s knit cotton t-shirt","attributes":{"material":"100% cotton"}}'

Runs against the offline mock if ANTHROPIC_API_KEY is unset.
"""
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from hts_pga_classifier import classify, DEFAULT_MODEL

app = FastAPI(title="HTS + PGA Classifier", version="0.1.0")


class ClassifyRequest(BaseModel):
    description: str = Field(..., description="Product description")
    attributes: Optional[dict] = Field(default=None,
        description="Optional facts: material, intended_use, country_of_origin, ...")
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    confidence_threshold: float = 0.8


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/classify")
def classify_endpoint(req: ClassifyRequest):
    return classify(
        req.description,
        attributes=req.attributes,
        model=req.model,
        effort=req.effort,
        confidence_threshold=req.confidence_threshold,
    )
