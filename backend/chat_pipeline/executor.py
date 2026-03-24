import sqlite3
from typing import Dict, Any, Tuple, List
from graph_service import GraphService
from chat_pipeline.planner import QueryPlan, QueryIntent

def execute_query_plan(plan: QueryPlan, service: GraphService, db_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Executes the query plan against the underlying data.
    Returns a tuple of (execution_result_dict, highlight_nodes_list)
    """
    intent = plan.intent
    
    if intent == QueryIntent.TRACE_FLOW:
        return _execute_trace(plan, service)
        
    elif intent == QueryIntent.BROKEN_FLOW:
        return _execute_broken_flows(service)
        
    elif intent == QueryIntent.ENTITY_LOOKUP:
        return _execute_entity_lookup(plan, service)
        
    elif intent == QueryIntent.AGGREGATION:
        return _execute_aggregation(plan, db_path)
        
    else:
        return {"error": "Unknown or unsupported intent."}, []

def _execute_trace(plan: QueryPlan, service: GraphService) -> Tuple[Dict[str, Any], List[str]]:
    if not plan.document_id:
        return {"error": "Trace requested but no document ID provided in the query."}, []
        
    target_id = plan.document_id
    doc_type = plan.entity_type or ""
    
    if "billing" in doc_type.lower() or target_id.startswith("9"):
        # Attempt to trace an invoice backwards
        billing_doc = target_id.replace("BILL_", "", 1)
        trace_result = service.trace_invoice_to_order(billing_doc)
        if not trace_result:
            return {"error": f"Could not trace billing document {billing_doc}."}, []
            
        highlight_nodes = [f"BILL_{billing_doc}"]
        for nodes in trace_result.values():
            highlight_nodes.extend(nodes)
        return trace_result, highlight_nodes
        
    else:
        # Default to tracing sales order forward
        so_num = target_id.replace("SO_", "", 1)
        trace_result = service.trace_sales_order(so_num)
        if not trace_result:
            return {"error": f"Could not trace sales order {so_num}."}, []
            
        highlight_nodes = []
        for nodes in trace_result.values():
            highlight_nodes.extend(nodes)
        return trace_result, highlight_nodes

def _execute_broken_flows(service: GraphService) -> Tuple[Dict[str, Any], List[str]]:
    broken = service.find_broken_flows(limit=20)
    if not broken:
        return {"result": "No broken flows found."}, []
        
    highlight_nodes = [b["sales_order_node"] for b in broken]
    return {"broken_flows": broken}, highlight_nodes

def _execute_entity_lookup(plan: QueryPlan, service: GraphService) -> Tuple[Dict[str, Any], List[str]]:
    if not plan.document_id:
        return {"error": "Entity lookup requested but no document ID provided."}, []
        
    # Standardize the ID based on entity type guessing
    raw_id = plan.document_id
    if plan.entity_type == "SalesOrder" and not raw_id.startswith("SO_"):
        raw_id = f"SO_{raw_id}"
    elif plan.entity_type == "BillingDocument" and not raw_id.startswith("BILL_"):
        raw_id = f"BILL_{raw_id}"
        
    node_data = service.get_node(raw_id)
    if not node_data:
        # If didn't find specific node type, try to find any node matching the document_id (naive search)
        for nid, attrs in service.graph.nodes(data=True):
            if str(raw_id) in nid:
                node_data = attrs
                raw_id = nid
                break
                
    if not node_data:
        return {"error": f"Could not find entity matching ID {plan.document_id}."}, []
        
    return node_data, [raw_id]

def _execute_aggregation(plan: QueryPlan, db_path: str) -> Tuple[Dict[str, Any], List[str]]:
    query_target = (plan.aggregation_target or "").lower()
    
    # Generic SQL handler for common aggregations. In a real system you'd use LLM text-to-SQL or mapped templates.
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        if "product" in query_target and ("billing" in query_target or "invoice" in query_target):
            sql = '''
            SELECT material as Product, COUNT(DISTINCT billingDocument) as DocumentCount
            FROM billing_document_items
            GROUP BY material
            ORDER BY DocumentCount DESC
            LIMIT 5
            '''
            rows = conn.execute(sql).fetchall()
            results = [dict(row) for row in rows]
            
            # The top products can be highlighted
            highlight_nodes = [f"PROD_{row['Product']}" for row in results if row['Product']]
            return {"top_products_by_billing": results}, highlight_nodes
            
        else:
            # Fallback simple aggregation
            sql = 'SELECT COUNT(*) as count FROM "sales_order_headers"'
            rows = conn.execute(sql).fetchall()
            return {"sales_order_total_count": rows[0]["count"], "message": "Generic aggregation fallback due to vague target."}, []
