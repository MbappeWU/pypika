import unittest

from pypika import QmarkParameter, Table
from pypika.analytics import Count
from pypika.dialects import MSSQLQuery
from pypika.utils import QueryException


class SelectTests(unittest.TestCase):
    def test_normal_select(self):
        q = MSSQLQuery.from_("abc").select("def")

        self.assertEqual('SELECT "def" FROM "abc"', str(q))

    def test_distinct_select(self):
        q = MSSQLQuery.from_("abc").select("def").distinct()

        self.assertEqual('SELECT DISTINCT "def" FROM "abc"', str(q))

    def test_top_distinct_select(self):
        q = MSSQLQuery.from_("abc").select("def").top(10).distinct()

        self.assertEqual('SELECT DISTINCT TOP (10) "def" FROM "abc"', str(q))

    def test_top_select(self):
        q = MSSQLQuery.from_("abc").select("def").top(10)

        self.assertEqual('SELECT TOP (10) "def" FROM "abc"', str(q))

    def test_top_with_ties_select(self):
        q = MSSQLQuery.from_("abc").select("def").top(10, with_ties=True)

        self.assertEqual('SELECT TOP (10) WITH TIES "def" FROM "abc"', str(q))

    def test_top_percent_select(self):
        q = MSSQLQuery.from_("abc").select("def").top(10, percent=True)

        self.assertEqual('SELECT TOP (10) PERCENT "def" FROM "abc"', str(q))

    def test_top_percent_invalid_range(self):
        for invalid_top in [-1, 101]:
            with self.assertRaisesRegex(
                QueryException, "TOP value must be between 0 and 100 when `percent` is specified"
            ):
                MSSQLQuery.from_("abc").select("def").top(invalid_top, percent=True)

    def test_top_select_non_int(self):
        with self.assertRaisesRegex(QueryException, "TOP value must be an integer"):
            MSSQLQuery.from_("abc").select("def").top("a")

    def test_limit(self):
        q = MSSQLQuery.from_("abc").select("def").orderby("def").limit(10)

        self.assertEqual('SELECT "def" FROM "abc" ORDER BY "def" OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY', str(q))

    def test_offset(self):
        q = MSSQLQuery.from_("abc").select("def").orderby("def").offset(10)

        self.assertEqual('SELECT "def" FROM "abc" ORDER BY "def" OFFSET 10 ROWS', str(q))

    def test_limit_with_offset(self):
        q = MSSQLQuery.from_("abc").select("def").orderby("def").limit(10).offset(10)

        self.assertEqual('SELECT "def" FROM "abc" ORDER BY "def" OFFSET 10 ROWS FETCH NEXT 10 ROWS ONLY', str(q))

    def test_groupby_alias_False_does_not_group_by_alias_with_standard_query(self):
        t = Table('table1')
        col = t.abc.as_('a')
        q = MSSQLQuery.from_(t).select(col, Count('*')).groupby(col)

        self.assertEqual('SELECT "abc" "a",COUNT(\'*\') FROM "table1" GROUP BY "abc"', str(q))

    def test_groupby_alias_False_does_not_group_by_alias_when_subqueries_are_present(self):
        t = Table('table1')
        subquery = MSSQLQuery.from_(t).select(t.abc)
        col = subquery.abc.as_('a')
        q = MSSQLQuery.from_(subquery).select(col, Count('*')).groupby(col)

        self.assertEqual(
            'SELECT "sq0"."abc" "a",COUNT(\'*\') FROM (SELECT "abc" FROM "table1") "sq0" GROUP BY "sq0"."abc"', str(q)
        )


class DeleteTests(unittest.TestCase):
    def test_delete_aliased_target(self):
        customers = Table("customers").as_("c")

        query = MSSQLQuery.from_(customers).where(customers.id == 1).delete()

        self.assertEqual('DELETE "c" FROM "customers" "c" WHERE "c"."id"=1', str(query))

    def test_delete_aliased_target_with_schema_and_custom_quotes(self):
        customers = Table("customers", schema="sales").as_("customer alias")

        query = MSSQLQuery.from_(customers).delete()

        self.assertEqual(
            "DELETE 'customer alias' FROM `sales`.`customers` AS 'customer alias'",
            query.get_sql(quote_char="`", alias_quote_char="'", as_keyword=True),
        )

    def test_delete_target_falls_back_to_quote_char_for_empty_alias_quote_char(self):
        customers = Table("customers").as_("c")

        query = MSSQLQuery.from_(customers).delete()

        self.assertEqual('DELETE "c" FROM "customers" "c"', query.get_sql(alias_quote_char=""))

    def test_delete_target_and_source_quote_complex_alias_consistently(self):
        customers = Table("customers").as_('customer "alias"')

        query = MSSQLQuery.from_(customers).delete()

        self.assertEqual(
            'DELETE "customer ""alias""" FROM "customers" "customer ""alias"""',
            query.get_sql(alias_quote_char=""),
        )

    def test_delete_aliased_target_with_join(self):
        customers = Table("customers").as_("c")
        orders = Table("orders").as_("o")

        query = MSSQLQuery.from_(customers).join(orders).on(customers.id == orders.customer_id).delete()

        self.assertEqual('DELETE "c" FROM "customers" "c" JOIN "orders" "o" ON "c"."id"="o"."customer_id"', str(query))

    def test_delete_unaliased_target_with_join_declares_target_and_source(self):
        customers = Table("customers")
        orders = Table("orders").as_("o")

        query = MSSQLQuery.from_(customers).join(orders).on(customers.id == orders.customer_id).delete()

        self.assertEqual(
            'DELETE FROM "customers" FROM "customers" JOIN "orders" "o" ON "customers"."id"="o"."customer_id"',
            str(query),
        )

    def test_delete_unaliased_target_is_unchanged(self):
        query = MSSQLQuery.from_(Table("customers")).delete()

        self.assertEqual('DELETE FROM "customers"', str(query))

    def test_delete_from_mssql_table_entry_point(self):
        customers = Table("customers", query_cls=MSSQLQuery).as_("c")

        query = MSSQLQuery.from_(customers).delete()

        self.assertEqual('DELETE "c" FROM "customers" "c"', str(query))

    def test_delete_builder_reuse_keeps_target_alias(self):
        customers = Table("customers").as_("c")
        query = MSSQLQuery.from_(customers).delete()

        self.assertEqual('DELETE "c" FROM "customers" "c"', str(query))
        self.assertEqual('DELETE "c" FROM "customers" "c" WHERE "c"."id"=1', str(query.where(customers.id == 1)))

    def test_select_from_subquery_does_not_render_parameters_twice(self):
        customers = Table("customers")
        inner_query = MSSQLQuery.from_(customers).select(customers.id).where(customers.status == "active")
        query = MSSQLQuery.from_(inner_query).select("*")
        parameter = QmarkParameter()

        sql = query.get_sql(parameter=parameter)

        self.assertEqual('SELECT * FROM (SELECT "id" FROM "customers" WHERE "status"=?) "sq0"', sql)
        self.assertEqual(["active"], parameter.get_parameters())
