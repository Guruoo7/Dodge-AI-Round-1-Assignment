import os
import json
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import google.generativeai as genai

# Configure Gemini AI
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class QueryIntent(str, Enum):
    AGGREGATION = "AGGREGATION"
    TRACE_FLOW = "TRACE_FLOW"
    BROKEN_FLOW = "BROKEN_FLOW"
    ENTITY_LOOKUP = "ENTITY_LOOKUP"
    UNKNOWN = "UNKNOWN"

class QueryPlan(BaseModel):
    intent: QueryIntent = Field(description="The detected intent of the user's query.")
    entity_type: Optional[str] = Field(None, description="The type of entity, e.g., 'SalesOrder', 'BillingDocument', 'Product'")
    document_id: Optional[str] = Field(None, description="The ID of the document or entity, if mentioned (e.g., 90012345).")
    aggregation_target: Optional[str] = Field(None, description="What the user wants to aggregate or count, if applicable.")
    reasoning: str = Field(description="A brief explanation of why this intent and parameters were chosen.")

def plan_query(user_query: str) -> QueryPlan:
    """
    Uses Gemini AI to parse the natural language query into a structured QueryPlan.
    """
    if not api_key:
        # Fallback to rule-based parsing if no API key is set
        return _rule_based_fallback(user_query)
        
    system_instruction = """
    You are an AI assistant for an SAP Order-to-Cash Graph Database.
    Your job is to analyze the user's natural language query and map it to exactly one of the known intents.
    
    INTENTS:
    - TRACE_FLOW: Tracing the full flow of a specific document (e.g., "Trace sales order 12345", "What happened to billing doc 9001").
    - BROKEN_FLOW: Finding broken or incomplete flows (e.g., "Find orders that were delivered but not billed").
    - ENTITY_LOOKUP: Getting details for a specific entity without tracing its whole flow (e.g., "Show me details for product PRD_1").
    - AGGREGATION: Counting or aggregating data across the graph (e.g., "Which products have the most billing documents?").
    - UNKNOWN: Use only if the query cannot be mapped to the above.
    
    Extract the 'document_id' and 'entity_type' if one is explicitly mentioned in the query. For trace queries, you typically need to identify the document_id (e.g. 12345, SO_1001, BILL_999).
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
        response = model.generate_content(
            user_query,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=QueryPlan,
                temperature=0.1,
            ),
        )
        
        # Parse the JSON string into the Pydantic model
        result_json = json.loads(response.text)
        return QueryPlan(**result_json)
        
    except Exception as e:
        print(f"Error calling Gemini AI: {e}")
        return _rule_based_fallback(user_query)

def _rule_based_fallback(query: str) -> QueryPlan:
    """Fallback if Gemini API fails or isn't configured."""
    q = query.lower()
    plan = QueryPlan(intent=QueryIntent.UNKNOWN, reasoning="Rule-based fallback strategy used.")
    
    if "trace" in q or "flow of" in q:
        plan.intent = QueryIntent.TRACE_FLOW
        
        # Extract number if present
        import re
        match = re.search(r'\b\d+\b', q)
        if match:
            plan.document_id = match.group()
            
        if "sales order" in q:
            plan.entity_type = "SalesOrder"
        elif "billing" in q or "invoice" in q:
            plan.entity_type = "BillingDocument"
            
    elif "broken" in q or ("delivered" in q and "not billed" in q):
        plan.intent = QueryIntent.BROKEN_FLOW
    elif "which" in q or "count" in q or "most" in q or "highest" in q:
        plan.intent = QueryIntent.AGGREGATION
    elif "detail" in q or "show me" in q:
        plan.intent = QueryIntent.ENTITY_LOOKUP
        import re
        match = re.search(r'\b\d+\b', q)
        if match:
            plan.document_id = match.group()
            
    return plan
