import re
from typing import Tuple

# A basic rule-based guardrail system
# In a full production system, this could also use a fast LLM or embedding similarity
ALLOWED_TOPICS = [
    r"sales\s?order",
    r"billing",
    r"invoice",
    r"deliver",
    r"broken",
    r"flow",
    r"trace",
    r"product",
    r"customer",
    r"order\s?to\s?cash",
    r"o2c",
    r"plant",
    r"payment",
    r"journal",
]

def check_guardrails(query: str) -> Tuple[bool, str]:
    """
    Validates if the user query is relevant to the Order-to-Cash domain.
    Returns (is_valid, error_message).
    """
    if not query or len(query.strip()) < 3:
        return False, "Query is too short."

    query_lower = query.lower()
    
    # Check if it matches any domain keywords
    is_on_topic = any(re.search(pattern, query_lower) for pattern in ALLOWED_TOPICS)
    
    if not is_on_topic:
        return False, "I can only answer questions related to the Order-to-Cash process (Sales Orders, Billing, Deliveries, etc.)."
        
    # Check for obvious malicious patterns (SQL injection heuristics)
    sql_patterns = [r"drop\s+table", r"delete\s+from", r"insert\s+into", r"update\s+.*set"]
    if any(re.search(pattern, query_lower) for pattern in sql_patterns):
        return False, "Query contains disallowed database operations."

    return True, ""
