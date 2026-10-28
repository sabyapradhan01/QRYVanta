from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import create_adapter


class DatabaseView(QWidget):
    """Database Explorer bound to the currently active QRYVANTA profile."""

    def __init__(self):
        super().__init__()
        self.adapter = None
        self.profile = None
        self.password = ""
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("DATABASE EXPLORER")
        title.setObjectName("db_title")

        self.status = QLabel("LOGIN REQUIRED")
        self.refresh_button = QPushButton("⟳ REFRESH")
        self.refresh_button.clicked.connect(self.load_tables)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)
        header.addWidget(self.refresh_button)
        main_layout.addLayout(header)

        content = QHBoxLayout()

        table_panel = QFrame()
        table_panel.setObjectName("db_table_panel")
        table_layout = QVBoxLayout(table_panel)
        table_label = QLabel("TABLES")
        table_label.setObjectName("db_section")
        table_layout.addWidget(table_label)

        self.table_list = QListWidget()
        self.table_list.itemClicked.connect(self.load_selected_table)
        table_layout.addWidget(self.table_list)
        content.addWidget(table_panel, 1)

        data_panel = QFrame()
        data_panel.setObjectName("db_data_panel")
        data_layout = QVBoxLayout(data_panel)

        self.selected_table_label = QLabel("Select a table")
        self.selected_table_label.setObjectName("db_selected_table")
        data_layout.addWidget(self.selected_table_label)

        self.table_info = QLabel("")
        self.table_info.setObjectName("db_info")
        data_layout.addWidget(self.table_info)

        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.horizontalHeader().setStretchLastSection(True)
        data_layout.addWidget(self.data_table)

        content.addWidget(data_panel, 4)
        main_layout.addLayout(content, 1)

        self.setStyleSheet("""
            #db_title { font-size: 24px; font-weight: 900; color: #111111; }
            #db_section { font-size: 12px; font-weight: 900; color: #111111; }
            #db_selected_table { font-size: 22px; font-weight: 900; color: #111111; }
            #db_info { color: #444444; font-weight: 700; }
            #db_table_panel, #db_data_panel {
                background-color: #FFFFFF;
                border: 3px solid #111111;
            }
            QListWidget {
                background-color: #F6F1E8;
                border: 2px solid #111111;
                font-weight: 700;
                font-size: 13px;
            }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background-color: #CFFF3F; color: #111111; }
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F3F3F3;
                border: 2px solid #111111;
                gridline-color: #C8C8C8;
            }
            QHeaderView::section {
                background-color: #FF7FA4;
                color: #111111;
                border: 1px solid #111111;
                padding: 7px;
                font-weight: 900;
            }
            QPushButton {
                background-color: #CFFF3F;
                color: #111111;
                border: 3px solid #111111;
                padding: 8px 12px;
                font-weight: 900;
            }
        """)

    def set_profile(self, profile, password):
        self.profile = profile
        self.password = password
        self.adapter = create_adapter(
            profile.database_type,
            profile=profile,
            password=password,
        )
        self.status.setText(
            f"{self.adapter.name} • {profile.database}"
        )
        self.table_list.clear()
        self.data_table.clear()
        self.selected_table_label.setText("Select a table")
        self.table_info.setText("")
        self.load_tables()

    def clear_profile(self):
        self.adapter = None
        self.profile = None
        self.password = ""
        self.table_list.clear()
        self.data_table.clear()
        self.selected_table_label.setText("Select a table")
        self.table_info.setText("")
        self.status.setText("LOGIN REQUIRED")

    def load_tables(self):
        self.table_list.clear()
        if self.adapter is None:
            self.status.setText("LOGIN REQUIRED")
            return

        try:
            schema = self.adapter.get_schema()
            names = sorted(schema.tables.keys())
            for table_name in names:
                self.table_list.addItem(QListWidgetItem(table_name))
            self.status.setText(
                f"{self.adapter.name} • {self.profile.database} • {len(names)} tables"
            )
        except Exception as error:
            self.status.setText(f"Database error: {error}")

    def load_selected_table(self, item):
        table_name = item.text()
        self.selected_table_label.setText(table_name)
        if self.adapter is None:
            return

        connection = None
        cursor = None
        try:
            schema = self.adapter.get_schema()
            table = schema.get_table(table_name)
            query = self.adapter.sample_query(table_name, 500)
            result = self.adapter.execute(query)

            columns = result.columns
            rows = result.rows
            total_rows = table.row_count if table else None

            self.table_info.setText(
                f"Rows shown: {len(rows)}"
                + (f"    Estimated rows: {int(total_rows)}" if total_rows is not None else "")
                + f"    Columns: {len(columns)}"
            )

            self.data_table.clear()
            self.data_table.setRowCount(len(rows))
            self.data_table.setColumnCount(len(columns))
            self.data_table.setHorizontalHeaderLabels(columns)

            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    self.data_table.setItem(
                        row_index,
                        column_index,
                        QTableWidgetItem("" if value is None else str(value)),
                    )

            self.data_table.resizeColumnsToContents()

        except Exception as error:
            self.table_info.setText(f"Error: {error}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
