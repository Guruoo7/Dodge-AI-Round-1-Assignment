import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import networkx as nx


def normalize_value(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def node_id_customer(customer_id: str) -> str:
    return f"CUSTOMER_{customer_id}"


def node_id_address(address_id: str) -> str:
    return f"ADDR_{address_id}"


def node_id_sales_order(sales_order: str) -> str:
    return f"SO_{sales_order}"


def node_id_sales_order_item(sales_order: str, item: str) -> str:
    return f"SOI_{sales_order}_{item}"


def node_id_schedule_line(sales_order: str, item: str, schedule_line: str) -> str:
    return f"SCH_{sales_order}_{item}_{schedule_line}"


def node_id_delivery(delivery_document: str) -> str:
    return f"DEL_{delivery_document}"


def node_id_delivery_item(delivery_document: str, item: str) -> str:
    return f"DELI_{delivery_document}_{item}"


def node_id_billing_document(billing_document: str) -> str:
    return f"BILL_{billing_document}"


def node_id_billing_document_item(billing_document: str, item: str) -> str:
    return f"BILLI_{billing_document}_{item}"


def node_id_journal_entry(accounting_document: str) -> str:
    return f"JRN_{accounting_document}"


def node_id_payment(accounting_document: str) -> str:
    return f"PAY_{accounting_document}"


def node_id_product(product: str) -> str:
    return f"PROD_{product}"


def node_id_plant(plant: str) -> str:
    return f"PLANT_{plant}"


@dataclass
class EdgeDef:
    src: str
    dst: str
    relation: str


class GraphBuilder:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    def build(self) -> nx.MultiDiGraph:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            self._add_customers_and_addresses(conn)
            self._add_products(conn)
            self._add_plants(conn)
            self._add_sales_orders(conn)
            self._add_sales_order_items(conn)
            self._add_schedule_lines(conn)
            self._add_deliveries(conn)
            self._add_delivery_items(conn)
            self._add_billing_documents(conn)
            self._add_billing_items(conn)
            self._add_journal_entries(conn)
            self._add_payments(conn)
            self._add_cross_process_edges(conn)
        return self.graph

    def _add_node(self, node_id: str, node_type: str, attrs: Dict[str, object]) -> None:
        payload = {k: v for k, v in dict(attrs).items() if v is not None}
        payload["node_type"] = node_type
        self.graph.add_node(node_id, **payload)

    def _add_edge(self, src: str, dst: str, relation: str, attrs: Optional[Dict[str, object]] = None) -> None:
        if src not in self.graph or dst not in self.graph:
            return
        payload = {k: v for k, v in dict(attrs or {}).items() if v is not None}
        payload["relationship"] = relation
        payload["edge_type"] = relation
        self.graph.add_edge(src, dst, key=relation, **payload)

    def _rows(self, conn: sqlite3.Connection, sql: str) -> Iterable[sqlite3.Row]:
        return conn.execute(sql).fetchall()

    def _add_customers_and_addresses(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "business_partners"'):
            customer_id = normalize_value(row["businessPartner"])
            if not customer_id:
                continue
            nid = node_id_customer(customer_id)
            self._add_node(
                nid,
                "Customer",
                {
                    "businessPartner": customer_id,
                    "customer": normalize_value(row["customer"]),
                    "name": normalize_value(row["businessPartnerName"]),
                    "category": normalize_value(row["businessPartnerCategory"]),
                },
            )

        for row in self._rows(conn, 'SELECT * FROM "business_partner_addresses"'):
            address_id = normalize_value(row["addressId"])
            partner = normalize_value(row["businessPartner"])
            if not address_id:
                continue
            addr_nid = node_id_address(address_id)
            self._add_node(
                addr_nid,
                "Address",
                {
                    "addressId": address_id,
                    "businessPartner": partner,
                    "cityName": normalize_value(row["cityName"]) if "cityName" in row.keys() else None,
                    "country": normalize_value(row["country"]) if "country" in row.keys() else None,
                    "postalCode": normalize_value(row["postalCode"]) if "postalCode" in row.keys() else None,
                },
            )
            if partner:
                self._add_edge(node_id_customer(partner), addr_nid, "HAS_ADDRESS")

    def _add_products(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "products"'):
            product = normalize_value(row["product"])
            if not product:
                continue
            self._add_node(
                node_id_product(product),
                "Product",
                {
                    "product": product,
                    "baseUnit": normalize_value(row["baseUnit"]) if "baseUnit" in row.keys() else None,
                    "productType": normalize_value(row["productType"]) if "productType" in row.keys() else None,
                },
            )

    def _add_plants(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "plants"'):
            plant = normalize_value(row["plant"])
            if not plant:
                continue
            self._add_node(
                node_id_plant(plant),
                "Plant",
                {
                    "plant": plant,
                    "plantName": normalize_value(row["plantName"]) if "plantName" in row.keys() else None,
                },
            )

    def _add_sales_orders(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "sales_order_headers"'):
            so = normalize_value(row["salesOrder"])
            sold_to = normalize_value(row["soldToParty"])
            if not so:
                continue
            so_id = node_id_sales_order(so)
            self._add_node(
                so_id,
                "SalesOrder",
                {
                    "salesOrder": so,
                    "soldToParty": sold_to,
                    "salesOrderType": normalize_value(row["salesOrderType"]),
                    "creationDate": normalize_value(row["creationDate"]),
                    "totalNetAmount": normalize_value(row["totalNetAmount"]),
                    "transactionCurrency": normalize_value(row["transactionCurrency"]),
                },
            )
            if sold_to:
                self._add_edge(node_id_customer(sold_to), so_id, "PLACED")

    def _add_sales_order_items(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "sales_order_items"'):
            so = normalize_value(row["salesOrder"])
            item = normalize_value(row["salesOrderItem"])
            material = normalize_value(row["material"])
            plant = normalize_value(row["productionPlant"])
            if not so or not item:
                continue
            item_id = node_id_sales_order_item(so, item)
            self._add_node(
                item_id,
                "SalesOrderItem",
                {
                    "salesOrder": so,
                    "salesOrderItem": item,
                    "material": material,
                    "requestedQuantity": normalize_value(row["requestedQuantity"]),
                    "netAmount": normalize_value(row["netAmount"]),
                    "storageLocation": normalize_value(row["storageLocation"]),
                },
            )
            self._add_edge(node_id_sales_order(so), item_id, "HAS_ITEM")
            if material:
                self._add_edge(item_id, node_id_product(material), "FOR_PRODUCT")
            if plant:
                self._add_edge(item_id, node_id_plant(plant), "FROM_PLANT")

    def _add_schedule_lines(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "sales_order_schedule_lines"'):
            so = normalize_value(row["salesOrder"])
            item = normalize_value(row["salesOrderItem"])
            line = normalize_value(row["scheduleLine"])
            if not so or not item or not line:
                continue
            line_id = node_id_schedule_line(so, item, line)
            self._add_node(
                line_id,
                "ScheduleLine",
                {
                    "salesOrder": so,
                    "salesOrderItem": item,
                    "scheduleLine": line,
                    "confirmedDeliveryDate": normalize_value(row["confirmedDeliveryDate"]),
                    "confirmedQuantity": normalize_value(row["confdOrderQtyByMatlAvailCheck"]),
                },
            )
            self._add_edge(node_id_sales_order_item(so, item), line_id, "HAS_SCHEDULE_LINE")

    def _add_deliveries(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "outbound_delivery_headers"'):
            delivery = normalize_value(row["deliveryDocument"])
            if not delivery:
                continue
            self._add_node(
                node_id_delivery(delivery),
                "Delivery",
                {
                    "deliveryDocument": delivery,
                    "shippingPoint": normalize_value(row["shippingPoint"]),
                    "actualGoodsMovementDate": normalize_value(row["actualGoodsMovementDate"])
                    if "actualGoodsMovementDate" in row.keys()
                    else None,
                },
            )

    def _add_delivery_items(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "outbound_delivery_items"'):
            delivery = normalize_value(row["deliveryDocument"])
            item = normalize_value(row["deliveryDocumentItem"])
            ref_so = normalize_value(row["referenceSdDocument"])
            ref_so_item = normalize_value(row["referenceSdDocumentItem"])
            if not delivery or not item:
                continue
            di_id = node_id_delivery_item(delivery, item)
            self._add_node(
                di_id,
                "DeliveryItem",
                {
                    "deliveryDocument": delivery,
                    "deliveryDocumentItem": item,
                    "referenceSdDocument": ref_so,
                    "referenceSdDocumentItem": ref_so_item,
                    "material": normalize_value(row["material"]) if "material" in row.keys() else None,
                },
            )
            self._add_edge(di_id, node_id_delivery(delivery), "PART_OF_DELIVERY")
            if ref_so and ref_so_item:
                self._add_edge(
                    node_id_sales_order_item(ref_so, ref_so_item),
                    di_id,
                    "FULFILLED_BY",
                )

    def _add_billing_documents(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "billing_document_headers"'):
            bill = normalize_value(row["billingDocument"])
            accounting_doc = normalize_value(row["accountingDocument"])
            if not bill:
                continue
            self._add_node(
                node_id_billing_document(bill),
                "BillingDocument",
                {
                    "billingDocument": bill,
                    "billingDocumentType": normalize_value(row["billingDocumentType"]),
                    "accountingDocument": accounting_doc,
                    "soldToParty": normalize_value(row["soldToParty"]),
                    "totalNetAmount": normalize_value(row["totalNetAmount"]),
                },
            )

    def _add_billing_items(self, conn: sqlite3.Connection) -> None:
        for row in self._rows(conn, 'SELECT * FROM "billing_document_items"'):
            bill = normalize_value(row["billingDocument"])
            item = normalize_value(row["billingDocumentItem"])
            ref_del = normalize_value(row["referenceSdDocument"])
            ref_del_item = normalize_value(row["referenceSdDocumentItem"])
            if not bill or not item:
                continue
            bi_id = node_id_billing_document_item(bill, item)
            self._add_node(
                bi_id,
                "BillingDocumentItem",
                {
                    "billingDocument": bill,
                    "billingDocumentItem": item,
                    "referenceSdDocument": ref_del,
                    "referenceSdDocumentItem": ref_del_item,
                    "material": normalize_value(row["material"]),
                    "netAmount": normalize_value(row["netAmount"]),
                },
            )
            self._add_edge(bi_id, node_id_billing_document(bill), "PART_OF_BILLING")
            if ref_del and ref_del_item:
                self._add_edge(
                    node_id_delivery_item(ref_del, ref_del_item),
                    bi_id,
                    "BILLED_AS",
                )

    def _add_journal_entries(self, conn: sqlite3.Connection) -> None:
        seen = set()
        for row in self._rows(conn, 'SELECT * FROM "journal_entry_items_accounts_receivable"'):
            accounting_doc = normalize_value(row["accountingDocument"])
            if not accounting_doc or accounting_doc in seen:
                continue
            seen.add(accounting_doc)
            self._add_node(
                node_id_journal_entry(accounting_doc),
                "JournalEntry",
                {
                    "accountingDocument": accounting_doc,
                    "referenceDocument": normalize_value(row["referenceDocument"]),
                    "companyCode": normalize_value(row["companyCode"]),
                    "fiscalYear": normalize_value(row["fiscalYear"]),
                },
            )

    def _add_payments(self, conn: sqlite3.Connection) -> None:
        seen = set()
        for row in self._rows(conn, 'SELECT * FROM "payments_accounts_receivable"'):
            accounting_doc = normalize_value(row["accountingDocument"])
            if not accounting_doc or accounting_doc in seen:
                continue
            seen.add(accounting_doc)
            self._add_node(
                node_id_payment(accounting_doc),
                "Payment",
                {
                    "accountingDocument": accounting_doc,
                    "clearingAccountingDocument": normalize_value(row["clearingAccountingDocument"]),
                    "companyCode": normalize_value(row["companyCode"]),
                    "fiscalYear": normalize_value(row["fiscalYear"]),
                    "customer": normalize_value(row["customer"]),
                },
            )

    def _add_cross_process_edges(self, conn: sqlite3.Connection) -> None:
        # BillingDocument -> JournalEntry (POSTED_TO)
        for row in self._rows(conn, 'SELECT billingDocument, accountingDocument FROM "billing_document_headers"'):
            bill = normalize_value(row["billingDocument"])
            accounting_doc = normalize_value(row["accountingDocument"])
            if bill and accounting_doc:
                self._add_edge(
                    node_id_billing_document(bill),
                    node_id_journal_entry(accounting_doc),
                    "POSTED_TO",
                )

        # BillingDocument -> Payment (SETTLED_BY), linked by accounting document.
        for row in self._rows(
            conn,
            '''
            SELECT bh.billingDocument AS billingDocument, p.accountingDocument AS paymentDocument
            FROM "billing_document_headers" bh
            JOIN "payments_accounts_receivable" p
              ON bh.accountingDocument = p.accountingDocument
            ''',
        ):
            bill = normalize_value(row["billingDocument"])
            payment_doc = normalize_value(row["paymentDocument"])
            if bill and payment_doc:
                self._add_edge(
                    node_id_billing_document(bill),
                    node_id_payment(payment_doc),
                    "SETTLED_BY",
                )

