import argparse
import itertools
import json
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def flatten_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return value


def normalize_row(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): flatten_value(v) for k, v in obj.items()}


def singularize(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("s") and len(name) > 1:
        return name[:-1]
    return name


def infer_sqlite_type(values: Iterable[Any]) -> str:
    seen_int = False
    seen_real = False
    seen_other = False
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            seen_int = True
        elif isinstance(value, int):
            seen_int = True
        elif isinstance(value, float):
            seen_real = True
        else:
            seen_other = True
            break
    if seen_other:
        return "TEXT"
    if seen_real:
        return "REAL"
    if seen_int:
        return "INTEGER"
    return "TEXT"


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def key_like_columns(columns: Sequence[str]) -> List[str]:
    tokens = (
        "id",
        "number",
        "document",
        "order",
        "item",
        "partner",
        "customer",
        "product",
        "material",
        "delivery",
        "billing",
        "journal",
        "entry",
        "accounting",
        "plant",
        "location",
        "company",
        "fiscal",
        "year",
        "schedule",
    )
    return [c for c in columns if any(tok in c.lower() for tok in tokens)]


def normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def table_detail_score(table_name: str) -> int:
    tokens = ("item", "line", "assignment", "address", "schedule", "plant", "location", "description", "payment")
    name = table_name.lower()
    return sum(1 for tok in tokens if tok in name)


def preferred_table_key_columns(table: str, columns: Sequence[str]) -> List[str]:
    by_norm = {normalize_name(c): c for c in columns}
    normalized_cols = set(by_norm.keys())
    prefs: List[str] = []

    suffixes = (
        "_headers",
        "_header",
        "_items",
        "_item",
        "_lines",
        "_line",
        "_assignments",
        "_assignment",
        "_descriptions",
        "_description",
        "_cancellations",
    )
    core = table
    for suffix in suffixes:
        if core.endswith(suffix):
            core = core[: -len(suffix)]
            break

    core_norm = normalize_name(core)
    if core_norm in normalized_cols:
        prefs.append(by_norm[core_norm])

    # Domain-specific preferences first.
    if "address" in table.lower():
        for candidate in ("addressId", "address"):
            norm = normalize_name(candidate)
            if norm in normalized_cols:
                prefs.append(by_norm[norm])

    # Common business-doc IDs.
    for candidate in (
        "salesOrder",
        "billingDocument",
        "deliveryDocument",
        "businessPartner",
        "customer",
        "product",
        "material",
        "plant",
        "accountingDocument",
    ):
        norm = normalize_name(candidate)
        if norm in normalized_cols:
            prefs.append(by_norm[norm])

    return list(dict.fromkeys(prefs))


def uniqueness_ratio(rows: Sequence[Dict[str, Any]], cols: Sequence[str]) -> Tuple[float, bool]:
    seen = set()
    usable = 0
    for row in rows:
        key = []
        has_blank = False
        for col in cols:
            value = row.get(col)
            if is_blank(value):
                has_blank = True
                break
            key.append(str(value))
        if has_blank:
            continue
        usable += 1
        tup = tuple(key)
        if tup in seen:
            return 0.0, False
        seen.add(tup)
    if usable == 0:
        return 0.0, False
    return len(seen) / len(rows), usable == len(rows)


def infer_primary_key(table: str, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> List[str]:
    if not rows:
        return []

    singular = singularize(table)
    preferred = [
        "id",
        f"{singular}id",
        singular,
        f"{table}id",
        f"{table}number",
    ]
    lower_map = {c.lower(): c for c in columns}

    # Strong domain patterns first (items/lines style composite keys).
    for parent_col, item_col in (
        ("salesOrder", "salesOrderItem"),
        ("billingDocument", "billingDocumentItem"),
        ("deliveryDocument", "deliveryDocumentItem"),
    ):
        if parent_col in columns and item_col in columns:
            combo = [parent_col, item_col]
            if "scheduleLine" in columns:
                combo.append("scheduleLine")
            ratio, complete = uniqueness_ratio(rows, combo)
            if complete and ratio == 1.0:
                return combo

    for preferred_col in preferred_table_key_columns(table, columns):
        ratio, complete = uniqueness_ratio(rows, [preferred_col])
        if complete and ratio == 1.0:
            return [preferred_col]

    # Try high-confidence single-column primary keys first.
    for candidate in preferred:
        if candidate in lower_map:
            real = lower_map[candidate]
            ratio, complete = uniqueness_ratio(rows, [real])
            if complete and ratio == 1.0:
                return [real]

    keyish = key_like_columns(columns)
    if not keyish:
        keyish = list(columns)

    # Try all single columns first.
    best: Optional[Tuple[int, float, List[str]]] = None
    for col in columns:
        ratio, complete = uniqueness_ratio(rows, [col])
        if complete and ratio == 1.0:
            score = 100 if col in keyish else 80
            if best is None or score > best[0]:
                best = (score, ratio, [col])
    if best:
        return best[2]

    # Then try composite (2 columns, and 3 only when needed).
    combo_source = keyish[:10] if keyish else list(columns)[:10]
    for size in (2, 3):
        if len(combo_source) < size:
            continue
        for combo in itertools.combinations(combo_source, size):
            ratio, complete = uniqueness_ratio(rows, combo)
            if complete and ratio == 1.0:
                return list(combo)
        # Accept near-perfect uniqueness for composite if no perfect key exists.
        candidate_best: Optional[Tuple[float, Tuple[str, ...]]] = None
        for combo in itertools.combinations(combo_source, size):
            ratio, complete = uniqueness_ratio(rows, combo)
            if complete and ratio >= 0.98:
                if candidate_best is None or ratio > candidate_best[0]:
                    candidate_best = (ratio, combo)
        if candidate_best:
            return list(candidate_best[1])

    return []


def distinct_non_blank(rows: Sequence[Dict[str, Any]], col: str) -> Set[str]:
    result: Set[str] = set()
    for row in rows:
        value = row.get(col)
        if not is_blank(value):
            result.add(str(value))
    return result


def infer_foreign_keys(
    table_rows: Dict[str, List[Dict[str, Any]]],
    primary_keys: Dict[str, List[str]],
) -> Dict[str, List[Tuple[List[str], str, List[str]]]]:
    foreign_keys: Dict[str, List[Tuple[List[str], str, List[str]]]] = defaultdict(list)
    parent_pk_values: Dict[Tuple[str, str], Set[str]] = {}

    for parent_table, pk_cols in primary_keys.items():
        if len(pk_cols) == 1 and pk_cols[0] != "_surrogate_id":
            parent_pk_values[(parent_table, pk_cols[0])] = distinct_non_blank(table_rows[parent_table], pk_cols[0])

    for child_table, rows in table_rows.items():
        if not rows:
            continue
        child_columns = list(rows[0].keys())

        # Single-column FK inference.
        for child_col in child_columns:
            child_vals = distinct_non_blank(rows, child_col)
            if len(child_vals) < 2:
                continue

            best_match: Optional[Tuple[float, str, str]] = None
            for (parent_table, parent_col), parent_vals in parent_pk_values.items():
                if parent_table == child_table:
                    continue
                if not parent_vals or len(parent_vals) < len(child_vals):
                    continue
                if not child_vals.issubset(parent_vals):
                    continue
                score = len(child_vals) / max(1, len(parent_vals))
                if child_col == parent_col:
                    score += 1.0
                if child_col.lower().endswith("id") and parent_col.lower().endswith("id"):
                    score += 0.2
                if best_match is None or score > best_match[0]:
                    best_match = (score, parent_table, parent_col)

            if best_match is not None:
                _, parent_table, parent_col = best_match
                child_pk = set(primary_keys.get(child_table, []))
                parent_pk = set(primary_keys.get(parent_table, []))
                child_vals = distinct_non_blank(table_rows[child_table], child_col)
                parent_vals = distinct_non_blank(table_rows[parent_table], parent_col)

                # Avoid ambiguous 1:1 reciprocal links between peer/master tables.
                if (
                    child_col in child_pk
                    and parent_col in parent_pk
                    and child_vals == parent_vals
                    and len(table_rows[child_table]) == len(table_rows[parent_table])
                ):
                    if table_detail_score(child_table) <= table_detail_score(parent_table):
                        continue

                fk = ([child_col], parent_table, [parent_col])
                if fk not in foreign_keys[child_table]:
                    foreign_keys[child_table].append(fk)

        # Composite FK inference for parent composite PKs.
        for parent_table, parent_pk in primary_keys.items():
            if parent_table == child_table or len(parent_pk) <= 1:
                continue
            if any(col not in child_columns for col in parent_pk):
                continue

            parent_set = set()
            for parent_row in table_rows[parent_table]:
                key = tuple(str(parent_row.get(c)) for c in parent_pk)
                if any(is_blank(v) for v in key):
                    continue
                parent_set.add(key)

            child_set = set()
            for child_row in rows:
                key = tuple(str(child_row.get(c)) for c in parent_pk)
                if any(is_blank(v) for v in key):
                    continue
                child_set.add(key)

            if child_set and child_set.issubset(parent_set):
                fk = (list(parent_pk), parent_table, list(parent_pk))
                if fk not in foreign_keys[child_table]:
                    foreign_keys[child_table].append(fk)

    # Resolve direct reciprocal FK edges by keeping the more detailed child table as dependent.
    all_edges = []
    for child_table, refs in foreign_keys.items():
        for child_cols, parent_table, parent_cols in refs:
            all_edges.append((child_table, tuple(child_cols), parent_table, tuple(parent_cols)))

    edge_set = set(all_edges)
    to_remove = set()
    for child_table, child_cols, parent_table, parent_cols in all_edges:
        reverse = (parent_table, parent_cols, child_table, child_cols)
        if reverse in edge_set:
            child_score = table_detail_score(child_table)
            parent_score = table_detail_score(parent_table)
            if child_score < parent_score:
                to_remove.add((child_table, child_cols, parent_table, parent_cols))
            elif child_score > parent_score:
                to_remove.add(reverse)

    if to_remove:
        for child_table, child_cols, parent_table, parent_cols in to_remove:
            foreign_keys[child_table] = [
                fk
                for fk in foreign_keys[child_table]
                if not (
                    tuple(fk[0]) == child_cols and fk[1] == parent_table and tuple(fk[2]) == parent_cols
                )
            ]

    return foreign_keys


def topo_sort_tables(
    tables: Sequence[str],
    foreign_keys: Dict[str, List[Tuple[List[str], str, List[str]]]],
) -> Tuple[List[str], bool]:
    in_degree = {t: 0 for t in tables}
    graph = defaultdict(list)

    for child, refs in foreign_keys.items():
        for _, parent, _ in refs:
            if parent == child:
                continue
            graph[parent].append(child)
            in_degree[child] += 1

    queue = deque(sorted([t for t in tables if in_degree[t] == 0]))
    ordered = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for nxt in graph[node]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    has_cycle = len(ordered) != len(tables)
    if has_cycle:
        leftovers = [t for t in sorted(tables) if t not in set(ordered)]
        ordered.extend(leftovers)
    return ordered, has_cycle


def load_jsonl_tables(dataset_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    table_rows: Dict[str, List[Dict[str, Any]]] = {}
    for table_dir in sorted([p for p in dataset_dir.iterdir() if p.is_dir()]):
        all_rows: List[Dict[str, Any]] = []
        for file_path in sorted(table_dir.glob("*.jsonl")):
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    all_rows.append(normalize_row(obj))
        table_rows[table_dir.name] = all_rows
    return table_rows


def build_table_columns(rows: Sequence[Dict[str, Any]]) -> List[str]:
    cols: Set[str] = set()
    for row in rows:
        cols.update(row.keys())
    return sorted(cols)


def create_tables(
    conn: sqlite3.Connection,
    table_rows: Dict[str, List[Dict[str, Any]]],
    primary_keys: Dict[str, List[str]],
    foreign_keys: Dict[str, List[Tuple[List[str], str, List[str]]]],
) -> Dict[str, List[str]]:
    table_columns: Dict[str, List[str]] = {}

    for table, rows in table_rows.items():
        columns = build_table_columns(rows) if rows else []
        if not columns:
            continue

        pk_cols = primary_keys[table]
        use_surrogate = not pk_cols
        if use_surrogate:
            pk_cols = ["_surrogate_id"]
            primary_keys[table] = pk_cols
            columns = ["_surrogate_id"] + columns

        col_values = {col: [] for col in columns if col != "_surrogate_id"}
        for row in rows:
            for col in col_values:
                col_values[col].append(row.get(col))

        column_defs = []
        for col in columns:
            if col == "_surrogate_id":
                column_defs.append(f'{quote_ident(col)} INTEGER PRIMARY KEY AUTOINCREMENT')
            else:
                sqlite_type = infer_sqlite_type(col_values[col])
                column_defs.append(f"{quote_ident(col)} {sqlite_type}")

        if not use_surrogate and pk_cols:
            pk_expr = ", ".join(quote_ident(c) for c in pk_cols)
            column_defs.append(f"PRIMARY KEY ({pk_expr})")

        for child_cols, parent_table, parent_cols in foreign_keys.get(table, []):
            child_expr = ", ".join(quote_ident(c) for c in child_cols)
            parent_expr = ", ".join(quote_ident(c) for c in parent_cols)
            column_defs.append(
                f"FOREIGN KEY ({child_expr}) REFERENCES {quote_ident(parent_table)} ({parent_expr})"
            )

        ddl = f"CREATE TABLE IF NOT EXISTS {quote_ident(table)} (\n  " + ",\n  ".join(column_defs) + "\n)"
        conn.execute(ddl)
        table_columns[table] = columns

    return table_columns


def insert_data(
    conn: sqlite3.Connection,
    table_rows: Dict[str, List[Dict[str, Any]]],
    table_columns: Dict[str, List[str]],
    insert_order: Sequence[str],
) -> None:
    for table in insert_order:
        rows = table_rows.get(table, [])
        columns = table_columns.get(table, [])
        if not rows or not columns:
            continue

        insert_cols = [c for c in columns if c != "_surrogate_id"]
        if not insert_cols:
            continue

        placeholders = ", ".join("?" for _ in insert_cols)
        col_expr = ", ".join(quote_ident(c) for c in insert_cols)
        sql = f"INSERT OR REPLACE INTO {quote_ident(table)} ({col_expr}) VALUES ({placeholders})"

        values = []
        for row in rows:
            values.append([row.get(col) for col in insert_cols])

        conn.executemany(sql, values)


def print_report(
    table_rows: Dict[str, List[Dict[str, Any]]],
    primary_keys: Dict[str, List[str]],
    foreign_keys: Dict[str, List[Tuple[List[str], str, List[str]]]],
    insert_order: Sequence[str],
    had_cycle: bool,
) -> None:
    print("\nInference Report")
    print("-" * 80)
    for table in sorted(table_rows.keys()):
        pk = primary_keys.get(table, [])
        pk_text = ", ".join(pk) if pk else "(none)"
        print(f"Table: {table:45} Rows: {len(table_rows[table]):6} PK: {pk_text}")
        for child_cols, parent_table, parent_cols in foreign_keys.get(table, []):
            print(f"  FK: ({', '.join(child_cols)}) -> {parent_table} ({', '.join(parent_cols)})")
    print("-" * 80)
    print("Insert order:", " -> ".join(insert_order))
    if had_cycle:
        print("Warning: cycle detected in FK graph. Insert order included fallback tables.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load JSONL dataset into SQLite with inferred PK/FK.")
    parser.add_argument(
        "--dataset-dir",
        default=str((Path(__file__).resolve().parent.parent / "dataset")),
        help="Path to dataset root directory containing table subfolders.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str((Path(__file__).resolve().parent / "graph_data.db")),
        help="Path to output SQLite database",
    )
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir).resolve()
    db_path = Path(args.db_path).resolve()

    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    table_rows = load_jsonl_tables(dataset_dir)
    if not table_rows:
        raise RuntimeError(f"No tables found under dataset directory: {dataset_dir}")

    table_columns = {table: build_table_columns(rows) for table, rows in table_rows.items()}
    primary_keys = {table: infer_primary_key(table, rows, table_columns[table]) for table, rows in table_rows.items()}
    foreign_keys = infer_foreign_keys(table_rows, primary_keys)
    tables = sorted(table_rows.keys())
    insert_order, has_cycle = topo_sort_tables(tables, foreign_keys)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        create_table_columns = create_tables(conn, table_rows, primary_keys, foreign_keys)

        if has_cycle:
            conn.execute("PRAGMA foreign_keys = OFF")
            insert_data(conn, table_rows, create_table_columns, insert_order)
            conn.execute("PRAGMA foreign_keys = ON")
        else:
            insert_data(conn, table_rows, create_table_columns, insert_order)

        conn.commit()
    finally:
        conn.close()

    print_report(table_rows, primary_keys, foreign_keys, insert_order, has_cycle)
    print(f"\nSQLite database created at: {db_path}")


if __name__ == "__main__":
    main()

