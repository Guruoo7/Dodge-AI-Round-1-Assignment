# Data Model Validation Report

- Database: `G:\Projects\Graph Based Data Modeling and Query System\graph_data.db`

## Step 1: Verify schema and relationships

### Table row counts
- sales_order_headers: 100
- sales_order_items: 167
- sales_order_schedule_lines: 179
- outbound_delivery_headers: 86
- outbound_delivery_items: 137
- billing_document_headers: 163
- billing_document_items: 245
- journal_entry_items_accounts_receivable: 123
- payments_accounts_receivable: 120
- business_partners: 8
- business_partner_addresses: 8
- customer_company_assignments: 8
- customer_sales_area_assignments: 28
- products: 69
- product_descriptions: 69
- plants: 44
- product_plants: 3036
- product_storage_locations: 16723
- billing_document_cancellations: 80

### PK uniqueness checks
- PASS | sales_order_headers | PK(salesOrder) | total=100 distinct=100
- PASS | sales_order_items | PK(salesOrder, salesOrderItem) | total=167 distinct=167
- PASS | sales_order_schedule_lines | PK(salesOrder, salesOrderItem, scheduleLine) | total=179 distinct=179
- PASS | outbound_delivery_headers | PK(deliveryDocument) | total=86 distinct=86
- PASS | outbound_delivery_items | PK(deliveryDocument, deliveryDocumentItem) | total=137 distinct=137
- PASS | billing_document_headers | PK(billingDocument) | total=163 distinct=163
- PASS | billing_document_items | PK(billingDocument, billingDocumentItem) | total=245 distinct=245
- PASS | journal_entry_items_accounts_receivable | PK(accountingDocument) | total=123 distinct=123
- PASS | payments_accounts_receivable | PK(accountingDocument) | total=120 distinct=120
- PASS | business_partners | PK(businessPartner) | total=8 distinct=8
- PASS | business_partner_addresses | PK(addressId) | total=8 distinct=8
- PASS | customer_company_assignments | PK(customer) | total=8 distinct=8
- PASS | customer_sales_area_assignments | PK(_surrogate_id) | total=28 distinct=28
- PASS | products | PK(product) | total=69 distinct=69
- PASS | product_descriptions | PK(product) | total=69 distinct=69
- PASS | plants | PK(plant) | total=44 distinct=44
- PASS | product_plants | PK(plant, product) | total=3036 distinct=3036
- PASS | product_storage_locations | PK(plant, product, storageLocation) | total=16723 distinct=16723
- PASS | billing_document_cancellations | PK(billingDocument) | total=80 distinct=80

### Relationship join checks
- PASS | sales order header <-> items | child=sales_order_items parent=sales_order_headers missing_links=0
- WARN | sales order item <-> delivery items | child=outbound_delivery_items parent=sales_order_items missing_links=137
- WARN | delivery items <-> billing items | child=billing_document_items parent=outbound_delivery_items missing_links=245
- PASS | billing header <-> journal entries | child=journal_entry_items_accounts_receivable parent=billing_document_headers missing_links=0
- PASS | billing/payment references | child=payments_accounts_receivable parent=journal_entry_items_accounts_receivable missing_links=0

## Step 2: Clean PK/FK/Business reference mapping

Mapping file generated at `backend/data_model_mapping.csv`.

### Quick mapping summary
- `sales_order_headers` -> PK: salesOrder | FK: soldToParty -> business_partners.businessPartner | Business refs: soldToParty (customer)
- `sales_order_items` -> PK: salesOrder, salesOrderItem | FK: salesOrder -> sales_order_headers.salesOrder; material -> product_descriptions.product; productionPlant -> plants.plant | Business refs: (salesOrder, salesOrderItem) business key referenced by downstream docs
- `sales_order_schedule_lines` -> PK: salesOrder, salesOrderItem, scheduleLine | FK: salesOrder -> sales_order_headers.salesOrder; (salesOrder, salesOrderItem) -> sales_order_items(salesOrder, salesOrderItem) | Business refs: scheduleLine sequence per sales order item
- `outbound_delivery_headers` -> PK: deliveryDocument | FK: shippingPoint -> plants.plant | Business refs: deliveryDocument used by delivery items and billing item references
- `outbound_delivery_items` -> PK: deliveryDocument, deliveryDocumentItem | FK: deliveryDocument -> outbound_delivery_headers.deliveryDocument | Business refs: (referenceSdDocument, referenceSdDocumentItem) -> sales_order_items(salesOrder, salesOrderItem); material, plant operational references
- `billing_document_headers` -> PK: billingDocument | FK: soldToParty -> business_partners.businessPartner; cancelledBillingDocument -> billing_document_cancellations.billingDocument | Business refs: billingDocument links to billing items and journal references
- `billing_document_items` -> PK: billingDocument, billingDocumentItem | FK: billingDocument -> billing_document_headers.billingDocument | Business refs: (referenceSdDocument, referenceSdDocumentItem) -> outbound_delivery_items(deliveryDocument, deliveryDocumentItem); material -> product_descriptions.product
- `journal_entry_items_accounts_receivable` -> PK: accountingDocument | FK: customer -> customer_company_assignments.customer | Business refs: referenceDocument -> billing_document_headers.billingDocument
- `payments_accounts_receivable` -> PK: accountingDocument | FK: accountingDocument -> journal_entry_items_accounts_receivable.accountingDocument; customer -> customer_company_assignments.customer | Business refs: clearingAccountingDocument (business reference to cleared accounting docs)
- `business_partners` -> PK: businessPartner | FK: customer -> customer_company_assignments.customer | Business refs: master party for sold-to and customer references
- `business_partner_addresses` -> PK: addressId | FK: businessPartner -> business_partners.businessPartner | Business refs: address master per business partner
- `customer_company_assignments` -> PK: customer | FK: customer -> business_partners.businessPartner | Business refs: company code assignment for customer
- `customer_sales_area_assignments` -> PK: _surrogate_id | FK: customer -> customer_company_assignments.customer | Business refs: sales org/distribution channel/division business assignment
- `products` -> PK: product | FK: (none) | Business refs: material/product master
- `product_descriptions` -> PK: product | FK: product -> products.product | Business refs: text/description master
- `plants` -> PK: plant | FK: (none) | Business refs: plant master
- `product_plants` -> PK: plant, product | FK: plant -> plants.plant; product -> product_descriptions.product | Business refs: plant-product assignment
- `product_storage_locations` -> PK: plant, product, storageLocation | FK: (plant, product) -> product_plants(plant, product) | Business refs: inventory location key
- `billing_document_cancellations` -> PK: billingDocument | FK: billingDocument -> billing_document_headers.billingDocument | Business refs: cancellation records tied to billing docs
