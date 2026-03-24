import os
from typing import Dict, Any, List
import google.generativeai as genai
from chat_pipeline.planner import QueryPlan

api_key = os.getenv("GEMINI_API_KEY")

def format_response(query: str, plan: QueryPlan, raw_result: Dict[str, Any], highlight_nodes: List[str]) -> Dict[str, Any]:
    """
    Takes the execution results and formats the final payload for the frontend.
    Uses Gemini to generate a natural language summary of the raw data.
    """
    answer_text = "Here is the data you requested."
    
    if api_key and "error" not in raw_result:
        try:
            prompt = f"""
            You are a data assistant for an SAP Order-to-Cash system.
            The user asked: "{query}"
            The system interpreted the intent as: {plan.intent.value}
            The database returned the following RAW JSON data:
            {raw_result}
            
            Based ONLY on the raw JSON data above, write a brief, helpful natural language answer to the user's question.
            Do not include the JSON itself in your text answer, just summarize the findings. Keep it under 3 sentences.
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            answer_text = response.text.strip()
        except Exception as e:
            print(f"Error calling Gemini AI for formatting: {e}")
            answer_text = _fallback_format(plan, raw_result)
    elif "error" in raw_result:
        answer_text = f"I encountered an issue processing that: {raw_result['error']}"
    else:
        answer_text = _fallback_format(plan, raw_result)
            
    return {
        "query": query,
        "answer": answer_text,
        "intent": plan.intent.value,
        "plan": plan.model_dump(),
        "data": raw_result,
        "highlight_nodes": highlight_nodes
    }

def _fallback_format(plan: QueryPlan, result: Dict[str, Any]) -> str:
    if plan.intent.value == "TRACE_FLOW":
        return f"Found trace data for {plan.document_id}."
    elif plan.intent.value == "BROKEN_FLOW":
        return f"Found {len(result.get('broken_flows', []))} broken flow(s)."
    elif plan.intent.value == "AGGREGATION":
        return f"Here are the aggregation results: {result}"
    return "Here is the requested information."
