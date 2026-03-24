import argparse
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx

try:
    from graph_builder import (
        GraphBuilder,
        node_id_billing_document,
        node_id_sales_order,
        node_id_sales_order_item,
    )
except ModuleNotFoundError:
    from backend.graph_builder import (
        GraphBuilder,
        node_id_billing_document,
        node_id_sales_order,
        node_id_sales_order_item,
    )


class GraphService:
    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph

    def total_nodes(self) -> int:
        return self.graph.number_of_nodes()

    def total_edges(self) -> int:
        return self.graph.number_of_edges()

    def sample_node_metadata(self, limit: int = 5) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        for idx, node in enumerate(self.graph.nodes):
            if idx >= limit:
                break
            out[node] = dict(self.graph.nodes[node])
        return out

    def get_node(self, node_id: str) -> Optional[Dict[str, object]]:
        if node_id not in self.graph:
            return None
        payload = dict(self.graph.nodes[node_id])
        payload["id"] = node_id
        return payload

    def get_node_edges(self, node_id: str, limit: int = 100) -> Dict[str, List[Dict[str, object]]]:
        if node_id not in self.graph:
            return {"incoming": [], "outgoing": []}
        incoming: List[Dict[str, object]] = []
        outgoing: List[Dict[str, object]] = []

        for src, dst, data in self.graph.in_edges(node_id, data=True):
            if len(incoming) >= limit:
                break
            incoming.append(
                {
                    "source": src,
                    "target": dst,
                    "relationship": data.get("relationship"),
                    "edge_type": data.get("edge_type"),
                }
            )
        for src, dst, data in self.graph.out_edges(node_id, data=True):
            if len(outgoing) >= limit:
                break
            outgoing.append(
                {
                    "source": src,
                    "target": dst,
                    "relationship": data.get("relationship"),
                    "edge_type": data.get("edge_type"),
                }
            )
        return {"incoming": incoming, "outgoing": outgoing}

    # ── Overview: aggregated type-level graph ──────────────────────────
    def get_overview_graph(self) -> Dict[str, object]:
        """Return a schema-level overview graph: one meta-node per entity type,
        edges between types with counts."""
        type_counts: Dict[str, int] = {}
        for _, attrs in self.graph.nodes(data=True):
            nt = str(attrs.get("node_type", "Unknown"))
            type_counts[nt] = type_counts.get(nt, 0) + 1

        edge_type_pairs: Dict[tuple, int] = {}
        for src, dst, attrs in self.graph.edges(data=True):
            src_type = str(self.graph.nodes[src].get("node_type", "Unknown"))
            dst_type = str(self.graph.nodes[dst].get("node_type", "Unknown"))
            rel = str(attrs.get("relationship", "RELATED_TO"))
            key = (src_type, dst_type, rel)
            edge_type_pairs[key] = edge_type_pairs.get(key, 0) + 1

        nodes = []
        for nt, count in type_counts.items():
            nodes.append({
                "data": {
                    "id": nt,
                    "label": f"{nt}\n({count})",
                    "node_type": nt,
                    "count": count,
                    "is_overview": True,
                }
            })

        edges = []
        for (src_type, dst_type, rel), count in edge_type_pairs.items():
            edge_id = f"{src_type}|{rel}|{dst_type}"
            edges.append({
                "data": {
                    "id": edge_id,
                    "source": src_type,
                    "target": dst_type,
                    "label": f"{rel} ({count})",
                    "relationship": rel,
                    "count": count,
                }
            })

        return {"nodes": nodes, "edges": edges}

    # ── Trace: follow a sales order through the full O2C chain ───────
    def trace_sales_order(self, sales_order: str) -> Dict[str, List[str]]:
        so_id = node_id_sales_order(sales_order)
        if so_id not in self.graph:
            return {}

        result: Dict[str, List[str]] = {
            "sales_order": [so_id],
            "sales_order_items": [],
            "delivery_items": [],
            "deliveries": [],
            "billing_document_items": [],
            "billing_documents": [],
            "journal_entries": [],
            "payments": [],
            "products": [],
            "customers": [],
        }

        # Customer -> SO  (incoming PLACED edge)
        for src, _, data in self.graph.in_edges(so_id, data=True):
            if data.get("relationship") == "PLACED":
                result["customers"].append(src)

        # SO -> SOI  (HAS_ITEM)
        for _, dst, data in self.graph.out_edges(so_id, data=True):
            if data.get("relationship") == "HAS_ITEM":
                result["sales_order_items"].append(dst)

        # SOI -> Product (FOR_PRODUCT)
        for soi in result["sales_order_items"]:
            for _, dst, data in self.graph.out_edges(soi, data=True):
                if data.get("relationship") == "FOR_PRODUCT":
                    result["products"].append(dst)

        # SOI -> DeliveryItem  (FULFILLED_BY)
        for soi in result["sales_order_items"]:
            for _, dst, data in self.graph.out_edges(soi, data=True):
                if data.get("relationship") == "FULFILLED_BY":
                    result["delivery_items"].append(dst)

        # DeliveryItem -> Delivery  (PART_OF_DELIVERY)
        for di in result["delivery_items"]:
            for _, dst, data in self.graph.out_edges(di, data=True):
                if data.get("relationship") == "PART_OF_DELIVERY":
                    result["deliveries"].append(dst)

        # DeliveryItem -> BillingDocumentItem  (BILLED_AS)
        for di in result["delivery_items"]:
            for _, dst, data in self.graph.out_edges(di, data=True):
                if data.get("relationship") == "BILLED_AS":
                    result["billing_document_items"].append(dst)

        # BillingDocumentItem -> BillingDocument  (PART_OF_BILLING)
        for bi in result["billing_document_items"]:
            for _, dst, data in self.graph.out_edges(bi, data=True):
                if data.get("relationship") == "PART_OF_BILLING":
                    result["billing_documents"].append(dst)

        # BillingDocument -> JournalEntry (POSTED_TO), BillingDocument -> Payment (SETTLED_BY)
        for bill in result["billing_documents"]:
            for _, dst, data in self.graph.out_edges(bill, data=True):
                rel = data.get("relationship")
                if rel == "POSTED_TO":
                    result["journal_entries"].append(dst)
                elif rel == "SETTLED_BY":
                    result["payments"].append(dst)

        for key in result:
            result[key] = sorted(set(result[key]))

        return result

    # ── Find broken / incomplete O2C flows ───────────────────────────
    def find_broken_flows(self, limit: int = 20) -> List[Dict[str, object]]:
        """Find sales orders missing downstream delivery or billing links."""
        broken: List[Dict[str, object]] = []
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get("node_type") != "SalesOrder":
                continue
            items = [dst for _, dst, d in self.graph.out_edges(node_id, data=True) if d.get("relationship") == "HAS_ITEM"]
            has_delivery = False
            has_billing = False
            for item in items:
                for _, dst, d in self.graph.out_edges(item, data=True):
                    rel = d.get("relationship")
                    if rel == "FULFILLED_BY":
                        has_delivery = True
                    # Check delivery items for billing
                    if rel == "FULFILLED_BY":
                        for _, dst2, d2 in self.graph.out_edges(dst, data=True):
                            if d2.get("relationship") == "BILLED_AS":
                                has_billing = True
            if not has_delivery or not has_billing:
                broken.append({
                    "sales_order_node": node_id,
                    "sales_order": attrs.get("salesOrder", node_id),
                    "has_delivery": has_delivery,
                    "has_billing": has_billing,
                    "item_count": len(items),
                })
            if len(broken) >= limit:
                break
        return broken

    def find_items_for_sales_order(self, sales_order: str) -> List[str]:
        so_id = node_id_sales_order(sales_order)
        if so_id not in self.graph:
            return []
        items: List[str] = []
        for _, dst, data in self.graph.out_edges(so_id, data=True):
            if data.get("relationship") == "HAS_ITEM":
                items.append(dst)
        return sorted(items)

    def get_product_for_sales_order_item(self, sales_order: str, item: str) -> List[str]:
        soi_id = node_id_sales_order_item(sales_order, item)
        if soi_id not in self.graph:
            return []
        products: List[str] = []
        for _, dst, data in self.graph.out_edges(soi_id, data=True):
            if data.get("relationship") == "FOR_PRODUCT":
                products.append(dst)
        return sorted(products)

    def trace_invoice_to_order(self, billing_document: str) -> Dict[str, List[str]]:
        bill_id = node_id_billing_document(billing_document)
        if bill_id not in self.graph:
            return {}

        result = {
            "billing_document_items": [],
            "delivery_items": [],
            "sales_order_items": [],
            "sales_orders": [],
            "journal_entries": [],
            "payments": [],
        }

        # BILL <- PART_OF_BILLING - BILLI
        for src, _, data in self.graph.in_edges(bill_id, data=True):
            if data.get("relationship") == "PART_OF_BILLING":
                result["billing_document_items"].append(src)

        # DELI -> BILLED_AS -> BILLI
        for bill_item in result["billing_document_items"]:
            for src, _, data in self.graph.in_edges(bill_item, data=True):
                if data.get("relationship") == "BILLED_AS":
                    result["delivery_items"].append(src)

        # SOI -> FULFILLED_BY -> DELI
        for deli_item in result["delivery_items"]:
            for src, _, data in self.graph.in_edges(deli_item, data=True):
                if data.get("relationship") == "FULFILLED_BY":
                    result["sales_order_items"].append(src)

        # SO -> HAS_ITEM -> SOI
        so_set = set()
        for soi in result["sales_order_items"]:
            for src, _, data in self.graph.in_edges(soi, data=True):
                if data.get("relationship") == "HAS_ITEM":
                    so_set.add(src)
        result["sales_orders"] = sorted(so_set)

        # BILL -> POSTED_TO -> JRN, BILL -> SETTLED_BY -> PAY
        for _, dst, data in self.graph.out_edges(bill_id, data=True):
            relation = data.get("relationship")
            if relation == "POSTED_TO":
                result["journal_entries"].append(dst)
            elif relation == "SETTLED_BY":
                result["payments"].append(dst)

        for key in result:
            result[key] = sorted(set(result[key]))

        return result


def first_node_of_type(graph: nx.MultiDiGraph, node_type: str) -> Optional[str]:
    for node, attrs in graph.nodes(data=True):
        if attrs.get("node_type") == node_type:
            return node
    return None


def build_report_text(
    db_path: Path,
    service: GraphService,
    sales_order_probe: Optional[str],
    billing_probe: Optional[str],
) -> str:
    lines: List[str] = []
    lines.append("# Graph Generation Report")
    lines.append("")
    lines.append(f"- Database: `{db_path}`")
    lines.append(f"- Total nodes: {service.total_nodes()}")
    lines.append(f"- Total edges: {service.total_edges()}")
    lines.append("")
    lines.append("## Sample node metadata")
    for node_id, attrs in service.sample_node_metadata(limit=5).items():
        lines.append(f"- `{node_id}`: {attrs}")
    lines.append("")
    lines.append("## Proof checks")

    if sales_order_probe:
        so = sales_order_probe.replace("SO_", "", 1)
        items = service.find_items_for_sales_order(so)
        lines.append(f"- Items for sales order `{so}`: {len(items)} -> {items[:10]}")
        if items:
            sample_item = items[0]
            parts = sample_item.split("_", 2)
            if len(parts) >= 3:
                products = service.get_product_for_sales_order_item(parts[1], parts[2])
                lines.append(f"- Product linked to `{sample_item}`: {products}")

    if billing_probe:
        bill = billing_probe.replace("BILL_", "", 1)
        trace = service.trace_invoice_to_order(bill)
        lines.append(f"- Invoice trace for `{bill}`:")
        for key, values in trace.items():
            lines.append(f"  - {key}: {len(values)} -> {values[:10]}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate graph from SQLite data.")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str((Path(__file__).resolve().parent / "graph_data.db")),
        help="Path to the input SQLite database",
    )
    parser.add_argument(
        "--report-path",
        default=str((Path(__file__).resolve().parent / "graph_generation_report.md")),
        help="Report output path.",
    )
    parser.add_argument(
        "--graphml-path",
        default=str((Path(__file__).resolve().parent / "graph_model.graphml")),
        help="GraphML output path.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    builder = GraphBuilder(str(db_path))
    graph = builder.build()
    service = GraphService(graph)

    sample_so = first_node_of_type(graph, "SalesOrder")
    sample_bill = first_node_of_type(graph, "BillingDocument")

    report_text = build_report_text(db_path, service, sample_so, sample_bill)
    report_path = Path(args.report_path).resolve()
    report_path.write_text(report_text, encoding="utf-8")

    # GraphML keeps the graph portable for graph tools.
    graphml_path = Path(args.graphml_path).resolve()
    nx.write_graphml(graph, graphml_path)

    print(f"Graph report: {report_path}")
    print(f"GraphML file: {graphml_path}")
    print(f"Nodes: {service.total_nodes()} | Edges: {service.total_edges()}")


if __name__ == "__main__":
    main()

