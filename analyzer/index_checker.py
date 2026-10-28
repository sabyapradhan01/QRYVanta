from database.db import get_connection


def get_indexes(table_name):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            INDEX_NAME,
            TABLE_NAME,
            COLUMN_NAME
        FROM USER_IND_COLUMNS
        WHERE TABLE_NAME = :table_name
        ORDER BY INDEX_NAME, COLUMN_POSITION
    """, {
        "table_name": table_name.upper()
    })

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    return rows


def has_index_on_column(table_name, column_name):
    indexes = get_indexes(table_name)

    for index in indexes:
        # Oracle returns:
        # (INDEX_NAME, TABLE_NAME, COLUMN_NAME)

        indexed_column = index[2]

        if indexed_column.upper() == column_name.upper():
            return True

    return False