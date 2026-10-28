from sqlglot import expressions as exp


_PREDICATE_TYPES = (
    exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
    exp.Between, exp.In, exp.Like, exp.ILike, exp.Is,
)

_ARITHMETIC = (
    exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod,
)


class QueryContext:
    def __init__(self, query, tree, database, schema, plan):
        self.query = query
        self.tree = tree
        self.database = database
        self.schema = schema
        self.plan = plan

        self.tables = []
        self.aliases = {}

        cte_names = {
            c.alias_or_name
            for c in tree.find_all(exp.CTE)
            if c.alias_or_name
        }

        for table in tree.find_all(exp.Table):
            name = table.name
            if not name or name in cte_names:
                continue
            if name not in self.tables:
                self.tables.append(name)
            alias = table.alias or name
            self.aliases[alias] = name
            self.aliases.setdefault(name, name)

        self.where = tree.find(exp.Where)
        self.select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
        self.order = tree.find(exp.Order)
        self.group = tree.args.get("group")
        self.limit = tree.args.get("limit")
        self.offset = tree.args.get("offset")

    def resolve_table(self, column):
        qualifier = column.table
        if qualifier:
            return self.aliases.get(qualifier, qualifier)
        if len(self.tables) == 1:
            return self.tables[0]
        for table in self.tables:
            if self.schema.has_column(table, column.name):
                return table
        return None

    def aliases_of(self, table):
        return {alias for alias, real_table in self.aliases.items() if real_table == table}

    def where_predicates(self):
        if not self.where:
            return []

        predicates = []
        for column in self.where.find_all(exp.Column):
            if isinstance(column.this, exp.Star):
                continue

            wrapped = False
            func = None
            op = None
            other = None
            nested = False

            node = column
            parent = column.parent
            while parent is not None and parent is not self.where:
                if isinstance(parent, (exp.Subquery, exp.Select)):
                    nested = True
                    break
                if isinstance(parent, _PREDICATE_TYPES):
                    op = type(parent).__name__.upper()
                    if isinstance(parent, exp.Binary):
                        other = parent.expression if parent.this is node else parent.this
                    break
                if isinstance(parent, exp.Func) or isinstance(parent, _ARITHMETIC):
                    if not wrapped:
                        wrapped = True
                        func = parent
                node = parent
                parent = parent.parent

            if nested or op is None:
                continue

            predicates.append({
                "table": self.resolve_table(column),
                "column": column.name,
                "op": op,
                "wrapped": wrapped,
                "func": func,
                "other": other,
            })
        return predicates

    def bare_filters(self, ops=None):
        return [
            predicate for predicate in self.where_predicates()
            if not predicate["wrapped"]
            and predicate["table"]
            and (ops is None or predicate["op"] in ops)
        ]

    def join_pairs(self):
        conditions = []
        for join in self.tree.find_all(exp.Join):
            on = join.args.get("on")
            if on:
                conditions.extend(on.find_all(exp.EQ))
        if self.where:
            conditions.extend(self.where.find_all(exp.EQ))

        pairs, seen = [], set()
        for eq in conditions:
            left, right = eq.left, eq.right
            if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                continue
            left_table = self.resolve_table(left)
            right_table = self.resolve_table(right)
            if not left_table or not right_table or left_table == right_table:
                continue
            pair = (left_table, left.name, right_table, right.name)
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
        return pairs

    def select_star_tables(self):
        if not self.select:
            return set()
        tables = set()
        for expression in self.select.expressions:
            if isinstance(expression, exp.Star):
                tables.update(self.tables)
            elif isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star):
                table = self.resolve_table(expression)
                if table:
                    tables.add(table)
        return tables

    def select_columns(self):
        if not self.select:
            return []
        result = []
        for expression in self.select.expressions:
            for column in expression.find_all(exp.Column):
                if isinstance(column.this, exp.Star):
                    continue
                table = self.resolve_table(column)
                if table:
                    result.append((table, column.name))
        return result

    def referenced_columns(self, table):
        if table in self.select_star_tables():
            return None
        columns = set()
        for column in self.tree.find_all(exp.Column):
            if isinstance(column.this, exp.Star):
                continue
            if self.resolve_table(column) == table:
                columns.add(column.name)
        return columns

    def has_where(self): return self.where is not None
    def has_order_by(self): return self.order is not None
    def has_group_by(self): return self.group is not None
    def has_limit(self): return self.limit is not None
    def has_offset(self): return self.offset is not None
    def has_join(self): return any(True for _ in self.tree.find_all(exp.Join))
    def join_count(self): return sum(1 for _ in self.tree.find_all(exp.Join))

    def has_distinct(self):
        return bool(self.select and self.select.args.get("distinct"))

    def aggregate_count(self):
        aggregate_types = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Median)
        return sum(1 for node in self.tree.walk() if isinstance(node, aggregate_types))

    def subquery_count(self):
        return sum(1 for _ in self.tree.find_all(exp.Subquery))

    def access_nodes(self, table=None):
        nodes = []
        for node in self.plan.nodes:
            if table is not None and node.table and node.table.upper() != table.upper():
                continue
            nodes.append({
                "kind": node.operation,
                "table": node.table,
                "index": node.index,
                "rows": node.estimated_rows,
                "cost": node.cost,
                "depth": node.depth,
                "text": node.details,
            })
        return nodes

    def has_table_scan(self, table=None):
        return any(
            node.operation == "TABLE_SCAN"
            and (table is None or (node.table and node.table.upper() == table.upper()))
            for node in self.plan.nodes
        )

    def has_plan_operation(self, operation):
        return self.plan.has_operation(operation)

    def has_sort(self): return bool(self.plan.sorts())
    def has_index_access(self): return bool(self.plan.index_scans())

    def first_rows(self):
        for node in self.plan.nodes:
            if node.estimated_rows is not None:
                return node.estimated_rows
        return None

    def table_row_count(self, table): return self.schema.row_count(table)
    def column_info(self, table, column): return self.schema.column_info(table, column)
    def indexes(self, table): return self.schema.index_definitions(table)
    def indexed_columns(self, table): return self.schema.indexed_columns(table)
    def indexes_leading_with(self, table, column): return self.schema.indexes_leading_with(table, column)
    def has_index(self, table, column): return self.schema.has_index_on_column(table, column)
