import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

try:
    from graph_builder import GraphBuilder
    from graph_service import GraphService
    from chat_pipeline.guardrails import check_guardrails
    from chat_pipeline.planner import plan_query
    from chat_pipeline.executor import execute_query_plan
    from chat_pipeline.formatter import format_response
except ModuleNotFoundError:
    from backend.graph_builder import GraphBuilder
    from backend.graph_service import GraphService
    from backend.chat_pipeline.guardrails import check_guardrails
    from backend.chat_pipeline.planner import plan_query
    from backend.chat_pipeline.executor import execute_query_plan
    from backend.chat_pipeline.formatter import format_response

class ChatQueryRequest(BaseModel):
    query: str


def make_app(db_path: str) -> FastAPI:
    app = FastAPI(title="Graph API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5180",
            "http://localhost:5180",
            "http://127.0.0.1:5181",
            "http://localhost:5181",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.db_path = str(Path(db_path).resolve())
    app.state.graph_service = None

    @app.on_event("startup")
    def startup_load_graph() -> None:
        builder = GraphBuilder(app.state.db_path)
        graph = builder.build()
        app.state.graph_service = GraphService(graph)

    def svc() -> GraphService:
        service = app.state.graph_service
        if service is None:
            raise HTTPException(status_code=503, detail="Graph not initialized.")
        return service

    def build_elements_for_nodes(
        service: GraphService,
        node_ids: Iterable[str],
    ) -> Dict[str, List[Dict[str, object]]]:
        node_id_set: Set[str] = set(node_ids)
        nodes: List[Dict[str, object]] = []
        edges: List[Dict[str, object]] = []
        seen_edges: Set[Tuple[str, str, str, str]] = set()

        for node_id in node_id_set:
            if node_id not in service.graph:
                continue
            attrs = dict(service.graph.nodes[node_id])
            label = str(attrs.get("name") or attrs.get("node_type") or node_id)
            node_type = str(attrs.get("node_type", "Unknown"))
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "label": label,
                        "node_type": node_type,
                        **attrs,
                    }
                }
            )

        for src, dst, key, attrs in service.graph.edges(keys=True, data=True):
            if src not in node_id_set or dst not in node_id_set:
                continue
            relation = str(attrs.get("relationship", key or "RELATED_TO"))
            edge_key = (src, relation, dst, str(key))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                {
                    "data": {
                        "id": f"{src}|{relation}|{dst}|{key}",
                        "source": src,
                        "target": dst,
                        "label": relation,
                        "relationship": relation,
                        **attrs,
                    }
                }
            )

        return {"nodes": nodes, "edges": edges}

    @app.get("/graph")
    def get_graph(include_elements: bool = Query(default=True)) -> Dict[str, object]:
        service = svc()
        node_type_counts: Dict[str, int] = {}
        edge_type_counts: Dict[str, int] = {}

        for _, attrs in service.graph.nodes(data=True):
            node_type = str(attrs.get("node_type", "Unknown"))
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1

        for _, _, attrs in service.graph.edges(data=True):
            edge_type = str(attrs.get("relationship", "Unknown"))
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1

        response: Dict[str, object] = {
            "db_path": app.state.db_path,
            "total_nodes": service.total_nodes(),
            "total_edges": service.total_edges(),
            "node_type_counts": dict(sorted(node_type_counts.items())),
            "edge_type_counts": dict(sorted(edge_type_counts.items())),
        }
        if include_elements:
            response["elements"] = build_elements_for_nodes(service, service.graph.nodes())
        return response

    @app.get("/graph/initial")
    def get_initial_graph(
        max_nodes: int = Query(default=100, ge=20, le=300),
    ) -> Dict[str, object]:
        service = svc()
        core_types = {"Customer", "SalesOrder", "Delivery", "BillingDocument", "Payment"}
        selected: List[str] = []

        for node_id, attrs in service.graph.nodes(data=True):
            if attrs.get("node_type") in core_types:
                selected.append(node_id)
            if len(selected) >= max_nodes:
                break

        elements = build_elements_for_nodes(service, selected)
        return {
            "max_nodes": max_nodes,
            "returned_nodes": len(elements["nodes"]),
            "returned_edges": len(elements["edges"]),
            "elements": elements,
        }

    @app.get("/graph/neighbors/{node_id}")
    def get_node_neighbors(
        node_id: str,
        hop: int = Query(default=1, ge=1, le=1),
        max_new_nodes: int = Query(default=40, ge=5, le=200),
    ) -> Dict[str, object]:
        service = svc()
        if node_id not in service.graph:
            raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

        # Hop is kept at 1 intentionally for safety and predictable expansion.
        _ = hop
        neighbor_ids = list(service.graph.predecessors(node_id)) + list(service.graph.successors(node_id))
        unique_neighbors: List[str] = []
        seen: Set[str] = {node_id}
        for nid in neighbor_ids:
            if nid in seen:
                continue
            seen.add(nid)
            unique_neighbors.append(nid)
            if len(unique_neighbors) >= max_new_nodes:
                break

        selected = [node_id] + unique_neighbors
        elements = build_elements_for_nodes(service, selected)
        return {
            "center_node": node_id,
            "max_new_nodes": max_new_nodes,
            "returned_nodes": len(elements["nodes"]),
            "returned_edges": len(elements["edges"]),
            "elements": elements,
        }

    @app.post("/chat/query")
    def chat_query(req: ChatQueryRequest) -> Dict[str, object]:
        """Conversational query endpoint with grounded graph execution."""
        service = svc()
        
        # 1. Guardrails
        is_valid, error_msg = check_guardrails(req.query)
        if not is_valid:
            return {
                "query": req.query,
                "answer": error_msg,
                "intent": "REJECTED",
                "plan": None,
                "data": None,
                "highlight_nodes": []
            }
            
        # 2. Planner
        plan = plan_query(req.query)
        
        # 3. Executor
        raw_result, highlight_nodes = execute_query_plan(plan, service, app.state.db_path)
        
        # 4. Formatter
        response_payload = format_response(req.query, plan, raw_result, highlight_nodes)
        
        return response_payload

    @app.get("/node/{node_id}")
    def get_node(node_id: str, edge_limit: int = Query(default=50, ge=1, le=1000)) -> Dict[str, object]:
        service = svc()
        node = service.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
        edges = service.get_node_edges(node_id, limit=edge_limit)
        return {"node": node, "edges": edges}

    @app.get("/graph/overview")
    def get_overview_graph() -> Dict[str, object]:
        """Return the schema-level aggregated business flow graph."""
        service = svc()
        return service.get_overview_graph()

    @app.get("/graph/trace/sales-order/{sales_order}")
    def trace_sales_order(sales_order: str) -> Dict[str, object]:
        """Trace a sales order forward through the O2C flow."""
        service = svc()
        so = sales_order.replace("SO_", "", 1) if sales_order.startswith("SO_") else sales_order
        trace = service.trace_sales_order(so)
        if not trace:
            raise HTTPException(
                status_code=404,
                detail=f"No sales order trace found for sales_order={sales_order}",
            )
        
        # Build subgraph elements for all traced nodes
        all_nodes = []
        for nodes_list in trace.values():
            all_nodes.extend(nodes_list)
        
        elements = build_elements_for_nodes(service, all_nodes)
        
        return {
            "sales_order": so,
            "trace": trace,
            "elements": elements
        }

    @app.get("/graph/trace/broken-flows")
    def get_broken_flows(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, object]:
        """Find sales orders with incomplete downstream flow."""
        service = svc()
        broken = service.find_broken_flows(limit=limit)
        
        # Extract sales order node IDs to build the graph
        so_nodes = [b["sales_order_node"] for b in broken]
        
        # We also want to include their items to show the "dead ends"
        all_nodes = list(so_nodes)
        for so_id in so_nodes:
            items = [dst for _, dst, d in service.graph.out_edges(so_id, data=True) if d.get("relationship") == "HAS_ITEM"]
            all_nodes.extend(items)
            
        elements = build_elements_for_nodes(service, all_nodes)
        
        return {
            "broken_flows_count": len(broken),
            "broken_flows": broken,
            "elements": elements
        }

    @app.get("/trace/{document_id}")
    def trace_document(document_id: str) -> Dict[str, object]:
        service = svc()
        billing_doc = document_id.replace("BILL_", "", 1) if document_id.startswith("BILL_") else document_id
        trace = service.trace_invoice_to_order(billing_doc)
        if not trace:
            raise HTTPException(
                status_code=404,
                detail=f"No billing document trace found for document_id={document_id}",
            )
            
        # Build subgraph elements to match the unified trace format
        all_nodes = []
        for nodes_list in trace.values():
            all_nodes.extend(nodes_list)
        # Also need to add the billing doc itself to the trace nodes
        # trace_invoice_to_order doesn't include the center node
        all_nodes.append(f"BILL_{billing_doc}")
            
        elements = build_elements_for_nodes(service, all_nodes)
            
        return {
            "document_id": document_id,
            "billing_document": billing_doc,
            "trace": trace,
            "elements": elements
        }

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run graph API server.")
    parser.add_argument(
        "--db-path",
        default=str((Path(__file__).resolve().parent.parent / "graph_data.db")),
        help="Path to SQLite database.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    app = make_app(str(db_path))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

