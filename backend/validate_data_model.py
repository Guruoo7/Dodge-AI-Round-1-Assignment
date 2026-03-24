import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


@dataclass
class TableModel:
    table: str
    primary_key: Sequence[str]
    foreign_keys: Sequence[str]
    business_references: Sequence[str]


MODEL_MAP: List[TableModel] = [
    TableModel(
        "sales_order_headers",
        ("salesOrder",),
        ("soldToParty -> business_partners.businessPartner",),
        ("soldToParty (customer)",),
    ),
    TableModel(
        "sales_order_items",
        ("salesOrder", "salesOrderItem"),
        (
            "salesOrder -> sales_order_headers.salesOrder",
            "material -> product_descriptions.product",
            "productionPlant -> plants.plant",
        ),
        ("(salesOrder, salesOrderItem) business key referenced by downstream docs",),
    ),
    TableModel(
        "sales_order_schedule_lines",
        ("salesOrder", "salesOrderItem", "scheduleLine"),
        (
            "salesOrder -> sales_order_headers.salesOrder",
            "(salesOrder, salesOrderItem) -> sales_order_items(salesOrder, salesOrderItem)",
        ),
        ("scheduleLine sequence per sales order item",),
    ),
    TableModel(
        "outbound_delivery_headers",
        ("deliveryDocument",),
        ("shippingPoint -> plants.plant",),
        ("deliveryDocument used by delivery items and billing item references",),
    ),
    TableModel(
        "outbound_delivery_items",
        ("deliveryDocument", "deliveryDocumentItem"),
        ("deliveryDocument -> outbound_delivery_headers.deliveryDocument",),
        (
            "(referenceSdDocument, referenceSdDocumentItem) -> sales_order_items(salesOrder, salesOrderItem)",
            "material, plant operational references",
        ),
    ),
    TableModel(
        "billing_document_headers",
        ("billingDocument",),
        (
            "soldToParty -> business_partners.businessPartner",
            "cancelledBillingDocument -> billing_document_cancellations.billingDocument",
        ),
        ("billingDocument links to billing items and journal references",),
    ),
    TableModel(
        "billing_document_items",
        ("billingDocument", "billingDocumentItem"),
        ("billingDocument -> billing_document_headers.billingDocument",),
        (
            "(referenceSdDocument, referenceSdDocumentItem) -> outbound_delivery_items(deliveryDocument, deliveryDocumentItem)",
            "material -> product_descriptions.product",
        ),
    ),
    TableModel(
        "journal_entry_items_accounts_receivable",
        ("accountingDocument",),
        ("customer -> customer_company_assignments.customer",),
        ("referenceDocument -> billing_document_headers.billingDocument",),
    ),
    TableModel(
        "payments_accounts_receivable",
        ("accountingDocument",),
        (
            "accountingDocument -> journal_entry_items_accounts_receivable.accountingDocument",
            "customer -> customer_company_assignments.customer",
        ),
        ("clearingAccountingDocument (business reference to cleared accounting docs)",),
    ),
    TableModel(
        "business_partners",
        ("businessPartner",),
        ("customer -> customer_company_assignments.customer",),
        ("master party for sold-to and customer references",),
    ),
    TableModel(
        "business_partner_addresses",
        ("addressId",),
        ("businessPartner -> business_partners.businessPartner",),
        ("address master per business partner",),
    ),
    TableModel(
        "customer_company_assignments",
        ("customer",),
        ("customer -> business_partners.businessPartner",),
        ("company code assignment for customer",),
    ),
    TableModel(
        "customer_sales_area_assignments",
        ("_surrogate_id",),
        ("customer -> customer_company_assignments.customer",),
        ("sales org/distribution channel/division business assignment",),
    ),
    TableModel(
        "products",
        ("product",),
        tuple(),
        ("material/product master",),
    ),
    TableModel(
        "product_descriptions",
        ("product",),
        ("product -> products.product",),
        ("text/description master",),
    ),
    TableModel(
        "plants",
        ("plant",),
        tuple(),
        ("plant master",),
    ),
    TableModel(
        "product_plants",
        ("plant", "product"),
        (
            "plant -> plants.plant",
            "product -> product_descriptions.product",
        ),
        ("plant-product assignment",),
    ),
    TableModel(
        "product_storage_locations",
        ("plant", "product", "storageLocation"),
        ("(plant, product) -> product_plants(plant, product)",),
        ("inventory location key",),
    ),
    TableModel(
        "billing_document_cancellations",
        ("billingDocument",),
        ("billingDocument -> billing_document_headers.billingDocument",),
        ("cancellation records tied to billing docs",),
    ),
]


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def check_pk_uniqueness(conn: sqlite3.Connection, table: str, pk: Sequence[str]) -> Tuple[int, int]:
    if not pk:
        return 0, 0
    cols = ", ".join(f'"{c}"' for c in pk)
    total = scalar(conn, f'SELECT COUNT(*) FROM "{table}"')
    distinct = scalar(conn, f'SELECT COUNT(*) FROM (SELECT DISTINCT {cols} FROM "{table}")')
    return total, distinct


def check_join_missing(
    conn: sqlite3.Connection,
    child_table: str,
    child_cols: Sequence[str],
    parent_table: str,
    parent_cols: Sequence[str],
) -> int:
    if len(child_cols) != len(parent_cols):
        raise ValueError("child_cols and parent_cols must have same length")

    on_expr = " AND ".join(
        f'c."{cc}" = p."{pc}"' for cc, pc in zip(child_cols, parent_cols)
    )
    not_null_expr = " AND ".join(f'c."{cc}" IS NOT NULL AND TRIM(CAST(c."{cc}" AS TEXT)) <> ""' for cc in child_cols)
    parent_null = " AND ".join(f'p."{pc}" IS NULL' for pc in parent_cols)

    sql = f"""
    SELECT COUNT(*)
    FROM "{child_table}" c
    LEFT JOIN "{parent_table}" p ON {on_expr}
    WHERE ({not_null_expr}) AND ({parent_null})
    """
    return scalar(conn, sql)


def verify_schema_and_relationships(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    results: Dict[str, List[str]] = {
        "table_counts": [],
        "pk_checks": [],
        "join_checks": [],
    }

    # Table counts
    for tm in MODEL_MAP:
        count = scalar(conn, f'SELECT COUNT(*) FROM "{tm.table}"')
        results["table_counts"].append(f"{tm.table}: {count}")

    # PK uniqueness
    for tm in MODEL_MAP:
        total, distinct = check_pk_uniqueness(conn, tm.table, tm.primary_key)
        status = "PASS" if total == distinct else "FAIL"
        pk_text = ", ".join(tm.primary_key)
        results["pk_checks"].append(
            f"{status} | {tm.table} | PK({pk_text}) | total={total} distinct={distinct}"
        )

    # Required join checks from user flow
    join_tests = [
        ("sales_order_items", ("salesOrder",), "sales_order_headers", ("salesOrder",), "sales order header <-> items"),
        ("outbound_delivery_items", ("referenceSdDocument", "referenceSdDocumentItem"), "sales_order_items", ("salesOrder", "salesOrderItem"), "sales order item <-> delivery items"),
        ("billing_document_items", ("referenceSdDocument", "referenceSdDocumentItem"), "outbound_delivery_items", ("deliveryDocument", "deliveryDocumentItem"), "delivery items <-> billing items"),
        ("journal_entry_items_accounts_receivable", ("referenceDocument",), "billing_document_headers", ("billingDocument",), "billing header <-> journal entries"),
        ("payments_accounts_receivable", ("accountingDocument",), "journal_entry_items_accounts_receivable", ("accountingDocument",), "billing/payment references"),
    ]

    for child_t, child_c, parent_t, parent_c, label in join_tests:
        missing = check_join_missing(conn, child_t, child_c, parent_t, parent_c)
        status = "PASS" if missing == 0 else "WARN"
        results["join_checks"].append(
            f"{status} | {label} | child={child_t} parent={parent_t} missing_links={missing}"
        )

    return results


def write_mapping_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["table", "primary_key", "foreign_keys", "business_reference_columns"])
        for tm in MODEL_MAP:
            writer.writerow(
                [
                    tm.table,
                    ", ".join(tm.primary_key),
                    "; ".join(tm.foreign_keys),
                    "; ".join(tm.business_references),
                ]
            )


def write_report_md(path: Path, db_path: Path, results: Dict[str, List[str]]) -> None:
    lines: List[str] = []
    lines.append("# Data Model Validation Report")
    lines.append("")
    lines.append(f"- Database: `{db_path}`")
    lines.append("")
    lines.append("## Step 1: Verify schema and relationships")
    lines.append("")
    lines.append("### Table row counts")
    for item in results["table_counts"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### PK uniqueness checks")
    for item in results["pk_checks"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Relationship join checks")
    for item in results["join_checks"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Step 2: Clean PK/FK/Business reference mapping")
    lines.append("")
    lines.append("Mapping file generated at `backend/data_model_mapping.csv`.")
    lines.append("")
    lines.append("### Quick mapping summary")
    for tm in MODEL_MAP:
        fk_text = "; ".join(tm.foreign_keys) if tm.foreign_keys else "(none)"
        br_text = "; ".join(tm.business_references) if tm.business_references else "(none)"
        lines.append(
            f"- `{tm.table}` -> PK: {', '.join(tm.primary_key)} | FK: {fk_text} | Business refs: {br_text}"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate loaded SQLite data model and generate mapping sheet.")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str((Path(__file__).resolve().parent / "graph_data.db")),
        help="Path to the SQLite database to validate",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backend_dir = Path(__file__).resolve().parent
    report_path = backend_dir / "data_model_validation_report.md"
    mapping_path = backend_dir / "data_model_mapping.csv"

    conn = sqlite3.connect(str(db_path))
    try:
        results = verify_schema_and_relationships(conn)
    finally:
        conn.close()

    write_mapping_csv(mapping_path)
    write_report_md(report_path, db_path, results)

    print(f"Validation report: {report_path}")
    print(f"Mapping sheet: {mapping_path}")


if __name__ == "__main__":
    main()

