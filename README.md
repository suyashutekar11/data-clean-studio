# Generic MySQL Data Quality & Cleaning Platform - Stage 1

This repository contains **Stage 1: MySQL Connection & Database Browser** foundation for a generic MySQL Data Quality and Cleaning Platform.

## 1. Proposed Technology Stack

- **UI & Presentation Layer:** [Streamlit](https://streamlit.io/) (Python)
  - Provides a clean, responsive, data-focused web UI without needing external build chains or Node.js dependencies.
- **Database Connectivity & Inspection:** [SQLAlchemy](https://www.sqlalchemy.org/) with `mysql-connector-python`
  - Handles robust connection management, timeout configuration, and database metadata extraction.
- **Data Handling:** [Pandas](https://pandas.pydata.org/)
  - Renders data previews and schema inspection structures cleanly in tabular format.
- **Testing:** [Pytest](https://docs.pytest.org/)
  - Unit and mock testing suite for connection handling and metadata extraction.

---

## 2. Project Structure

```
DATA CLEANING TOOL/
├── src/
│   ├── __init__.py
│   ├── connection.py        # Connection manager, engine builder, error handler
│   └── metadata.py          # Dynamic database, table, schema, & preview extractor
├── tests/
│   └── test_stage1.py       # Unit tests for Stage 1 connection & discovery modules
├── app.py                   # Streamlit web application interface
├── requirements.txt         # Python dependency definitions
└── README.md                # Stage 1 documentation and guide
```

---

## 3. How the MySQL Connection Works

1. The user inputs their MySQL credentials (**Host**, **Port**, **Username**, **Password**) into the UI sidebar.
2. Clicking **Test Connection** or **Connect** triggers `MySQLConnectionManager.test_connection()`.
3. The system constructs a SQLAlchemy connection URL (`mysql+mysqlconnector://...`) and attempts a low-overhead connection query (`SELECT 1`).
4. **Error Handling:** If connection fails, errors are intercepted and categorized:
   - **Invalid credentials** (Error 1045) -> Clear access denied error.
   - **Server unavailable/incorrect host or port** (Error 2002/2003) -> Network/unreachable server warning.
   - **Timeout** -> Timeout alert prompting credential and network check.
   - **Database error** (Error 1049) -> Database missing notification.

---

## 4. How Database / Table Discovery Works

The tool is **100% generic** and discovers schema structure dynamically via MySQL metadata:

1. **Database Discovery (`MySQLMetadataInspector.get_databases`):** Uses SQLAlchemy `inspect(engine).get_schema_names()` to dynamically retrieve all available databases/schemas on the server.
2. **Table Discovery (`MySQLMetadataInspector.get_tables`):** Uses `inspect(engine).get_table_names(schema=database)` to list all tables in the chosen database.
3. **Schema Inspection (`MySQLMetadataInspector.get_table_schema`):** Extracts column names, data types, nullability (`YES`/`NO`), primary keys (`PRIMARY KEY`), foreign keys (`FOREIGN KEY`), and default values.
4. **Data Preview (`MySQLMetadataInspector.get_table_preview`):** Queries `SELECT * FROM \`database\`.\`table\` LIMIT :limit` to safely preview sample rows without modifying data or lock tables.

---

## 5. Security & Architectural Standards

- **No Hard-coded Credentials:** Passwords and user credentials are provided interactively via masked password inputs.
- **No Password Logging:** Credentials remain in memory during session state only. No credentials are stored on disk or written to log files.
- **Stateless & Modular:** Separated connection logic (`connection.py`), metadata logic (`metadata.py`), and UI (`app.py`), allowing seamless addition of future cleaning/AI stages.

---

## 6. How to Install Dependencies

Ensure Python 3.9+ is installed, then run:

```bash
pip install -r requirements.txt
```

---

## 7. How to Run the Application

To launch the Streamlit interface:

```bash
streamlit run app.py
```

The application will launch in your browser at `http://localhost:8501`.

---

## 8. How to Test Stage 1

Run the pytest suite to verify connection handling and metadata discovery:

```bash
pytest tests/test_stage1.py
```

The test suite covers:
1. Connection test with invalid credentials handling.
2. Connection test with unreachable server/host handling.
3. Dynamic database listing and system DB filtering.
4. Table listing per schema.
5. Column schema inspection (data types, nullability, keys).
6. Table preview query execution.

---

## 9. Limitations & Stage 1 Decisions

- **ReadOnly Stage:** Stage 1 performs read-only inspection queries. No data modification or schema alteration is implemented.
- **Future Stages Ready:** No data cleaning, duplicate removal, AI/Gemini integration, or production modification logic has been added yet as requested.
