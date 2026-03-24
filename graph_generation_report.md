# Graph Generation Report

- Database: `G:\Projects\Graph Based Data Modeling and Query System\graph_data.db`
- Total nodes: 1449
- Total edges: 1413

## Sample node metadata
- `CUSTOMER_310000108`: {'businessPartner': '310000108', 'customer': '310000108', 'name': 'Cardenas, Parker and Avila', 'category': '2', 'node_type': 'Customer'}
- `CUSTOMER_310000109`: {'businessPartner': '310000109', 'customer': '310000109', 'name': 'Bradley-Kelley', 'category': '2', 'node_type': 'Customer'}
- `CUSTOMER_320000082`: {'businessPartner': '320000082', 'customer': '320000082', 'name': 'Nguyen-Davis', 'category': '2', 'node_type': 'Customer'}
- `CUSTOMER_320000083`: {'businessPartner': '320000083', 'customer': '320000083', 'name': 'Nelson, Fitzpatrick and Jordan', 'category': '2', 'node_type': 'Customer'}
- `CUSTOMER_320000085`: {'businessPartner': '320000085', 'customer': '320000085', 'name': 'Hawkins Ltd', 'category': '2', 'node_type': 'Customer'}

## Proof checks
- Items for sales order `740506`: 5 -> ['SOI_740506_10', 'SOI_740506_20', 'SOI_740506_30', 'SOI_740506_40', 'SOI_740506_50']
- Product linked to `SOI_740506_10`: ['PROD_S8907367001003']
- Invoice trace for `90504248`:
  - billing_document_items: 1 -> ['BILLI_90504248_10']
  - delivery_items: 0 -> []
  - sales_order_items: 0 -> []
  - sales_orders: 0 -> []
  - journal_entries: 1 -> ['JRN_9400000249']
  - payments: 0 -> []
