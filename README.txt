QRYVANTA — QUERY INTELLIGENCE STUDIO
====================================
USER GUIDE: FIND YOUR DATABASE CONNECTION DETAILS
Version: 1.1.0

Welcome to QRYVANTA!
QRYVANTA connects to Oracle, MySQL, and PostgreSQL databases so you can run SQL, view query results, and inspect lint/performance findings.

IMPORTANT BEFORE YOU START
--------------------------
• You need access to a database that you are authorized to use.
• QRYVANTA does not create a database account for you and cannot reveal a forgotten password.
• Ask your database administrator, teacher, lab assistant, or hosting provider for the host, port, service/database name, username, and password.
• If the database is on your own computer, Host is often localhost. If it is on another computer or a college/company server, use the server hostname or IP address provided by its administrator.
• TEST CONNECTION checks the details before you log in. If it fails, see TROUBLESHOOTING below.

------------------------------------------------------------
1. HOW TO SIGN IN TO QRYVANTA
------------------------------------------------------------
1. Open QRYVANTA.
2. Click LOGIN or SWITCH ACCOUNT, then choose ADD ACCOUNT if needed.
3. Select the correct database type: Oracle, MySQL, or PostgreSQL.
4. Enter the Host, Port, Service / Database, Username, Password, and Account name.
5. Click TEST CONNECTION.
6. If the test succeeds, click LOGIN. If you tick "Save this account", QRYVANTA can remember the profile for future sign-ins. Saved passwords are handled by your operating system's credential store.
7. After login, use the SQL Console to run a query. For example, `SELECT * FROM your_table;` Replace `your_table` with a table that exists in your database and that you have permission to read.

The Account name is only a label inside QRYVANTA (for example, "College PostgreSQL"). It is not your database username.

------------------------------------------------------------
2. ORACLE
------------------------------------------------------------
Where to find the details:

A) If your teacher/administrator gave you a connection sheet, use the values listed there.
B) In Oracle SQL Developer, open an existing connection and choose Properties/Edit Connection. Look for:
   • Username
   • Hostname
   • Port
   • Connection type and Service name (or SID, if your administrator specifically provided a SID)
C) If you do not have an existing connection, ask your Oracle DBA/teacher for the exact service name and login username. Do not guess the service name or use someone else's credentials.

QRYVANTA fields:
   Database             Oracle
   Host                 The Oracle database server, e.g. localhost for a local database
   Port                 Usually 1521, unless your administrator says otherwise
   Service / Database   The Oracle SERVICE NAME supplied by your administrator
   Username             Your Oracle database username
   Password             Your Oracle database password
   Account name         Any descriptive label you choose

Notes:
• Oracle XE 11g commonly uses service name XE, but other Oracle versions/installations may use a different service name. Confirm it before connecting.
• Oracle database login and the SQL*Plus console are separate requirements. For the Oracle console, QRYVANTA also needs a compatible Oracle Client/SQL*Plus installation on the computer.
• If QRYVANTA asks you to locate SQL*Plus, browse to the actual `sqlplus.exe` file in your Oracle installation's `bin` folder. The exact location varies by computer.
• If SQL*Plus is missing or Oracle Client libraries are incompatible, database sign-in or the SQL*Plus console may not work until the Oracle prerequisites are installed/configured.

------------------------------------------------------------
3. MYSQL
------------------------------------------------------------
Where to find the details:

A) In MySQL Workbench, select your saved connection and open its Edit Connection/settings screen.
B) Look for Hostname, Port, and Username. The configured/default port is usually 3306.
C) The database/schema name is the schema you have permission to use. It may appear in the SCHEMAS panel after connecting.
D) Workbench may save a password in its credential vault, but it might not show the saved password as readable text. If you do not know the password, ask the database administrator or reset it using the approved process.

QRYVANTA fields:
   Database             MySQL
   Host                 Hostname or server IP (localhost if MySQL is installed locally)
   Port                 Usually 3306
   Service / Database   The database/schema name
   Username             Your MySQL username
   Password             Your MySQL password
   Account name         Any descriptive label you choose

If you only have access to a remote MySQL server, the server administrator must allow your computer/network to connect. A correct password alone is not enough if network access is blocked.

------------------------------------------------------------
4. POSTGRESQL
------------------------------------------------------------
Where to find the details:

A) In pgAdmin, expand Servers, right-click your registered server, and choose Properties.
B) Under Connection, check Host name/address, Port, Maintenance database, and Username.
C) The maintenance database shown in pgAdmin is not necessarily the application database you want. Ask your administrator which database to use if you are unsure.
D) pgAdmin might save a password without displaying it. If you do not know it, ask the administrator or reset it using the approved process.

QRYVANTA fields:
   Database             PostgreSQL
   Host                 Host name/address (localhost if PostgreSQL is installed locally)
   Port                 Usually 5432
   Service / Database   The database name
   Username             Your PostgreSQL role/login name
   Password             Your PostgreSQL password
   Account name         Any descriptive label you choose

PostgreSQL permissions are granted separately from a successful connection. If login succeeds but reading a table returns "permission denied", ask the owner/administrator to grant your account the required access to that database, schema, and table.

------------------------------------------------------------
5. LOCAL DATABASE OR REMOTE DATABASE?
------------------------------------------------------------
LOCAL DATABASE (database installed on this same computer)
   Host is often: localhost
   Use the port and database/service name configured during installation.

REMOTE DATABASE (college, company, lab, cloud, or another PC)
   Host is the server hostname or IP address provided by your administrator.
   You may need a VPN, campus/company network, firewall rule, or allowlisted IP address.
   Do not enter localhost for a remote server: localhost means this computer.

------------------------------------------------------------
6. TROUBLESHOOTING
------------------------------------------------------------
"Connection refused" / timeout
   • Confirm the database server is running.
   • Check the hostname and port.
   • For remote databases, confirm VPN/network access and firewall rules with the administrator.

"Authentication failed" / "invalid username or password"
   • Check spelling, capitalization, and the correct database user.
   • Confirm the password with the database administrator. QRYVANTA cannot retrieve a forgotten password.

"Database / service does not exist"
   • Confirm the exact database name (MySQL/PostgreSQL) or Oracle service name.
   • Oracle service name and SID are not always interchangeable. Use the type of connection details your administrator provided.

"Permission denied" / "not authorized"
   • The account may connect successfully but lack privileges for a schema, table, or query.
   • Ask the database/table owner or administrator to grant only the access you need.

Oracle console says SQL*Plus is missing or cannot start
   • Install/configure a compatible Oracle Client and SQL*Plus version.
   • When requested, select the actual sqlplus.exe file from your Oracle installation.
   • Oracle Instant Client alone may not include SQL*Plus unless the SQL*Plus package is also installed.
   • Restart QRYVANTA after changing the Oracle installation or path settings.

QRYVANTA can connect but analysis fails
   • Make sure you are using the latest packaged version.
   • Save the full error text or a screenshot and send it to your QRYVANTA support contact.

------------------------------------------------------------
7. SAFE USE AND PRIVACY
------------------------------------------------------------
• Only connect to databases you are authorized to access.
• Never send your password in screenshots, public chats, source code, README files, or .env files.
• Do not share database credentials with classmates or colleagues; each person should use their own account where possible.
• Use a read-only account for query review when write access is not necessary.
• Be careful when executing INSERT, UPDATE, DELETE, DDL, stored procedures, or other statements that modify data. Confirm you are using the intended database before running them.
• Do not distribute your development .env file. It may contain private settings or credentials.

------------------------------------------------------------
QUICK REFERENCE — COMMON DEFAULT PORTS
------------------------------------------------------------
Oracle       1521
MySQL        3306
PostgreSQL   5432

These are common defaults, not guarantees. Use the port given by your database administrator.

QRYVANTA — Query Intelligence Studio


============================================================
QRYVANTA 1.1.0 - OFFLINE STUDY, DOWNLOADS AND DAY/NIGHT MODE
============================================================

NEW TOP-BAR CONTROLS
--------------------
? menu: LEARN, HELP, QUIZ, COMPETITIVE EXAM, DEVELOPED BY. These windows run from local packaged content; they do not require an internet connection.
DAY/NIGHT: switches the legibility palette while preserving the selected Neo-Brutalism, Cybercore, Swiss, Bento Grid or Cyberpunk theme identity. Both selected theme and day/night mode are saved in QSettings.
DOWNLOAD (inside the analyzer header): Database Table CSV, SQL Command History TXT, Processing Report PDF, Processing Report DOCX and Processing Report TXT. CSV contains the currently visible Database Explorer table and its column headers. The report describes only analysis data currently available; it does not fabricate elapsed time or actual-row counts.

OFFLINE LEARNING CONTENT
------------------------
LEARN includes SQL fundamentals, static linting vs performance analysis, SQLGlot parsing and ASTs, execution plans, indexes, joins, SARGability, optimization workflow, architecture, glossary, references, and explanations tied to every source rule SQL001-SQL015 and P001-P022.
The canonical question bank is learning_content.py. quiz_engine.py contains random selection, answer validation and scoring. feature_windows.py provides the user interface. The Quiz PDF is generated from the same QUESTION_BANK source so questions, choices, correct answers and explanations remain aligned. The Competitive Exam panel reuses the same original practice bank. These are original practice questions and are not represented as actual past-paper questions.

OPTIONAL LOCAL ASSETS
---------------------
The source ZIP currently has the QRYVANTA logo/icon assets, but did not include these optional files at the time of integration:
  assets/learn.mp4
  assets/Dev1.jpg
  assets/Dev2.jpg
  assets/fac.jpg
If provided, the video is used by the local player and the portraits are used in DEVELOPED BY. `assets/fac.jpg` is the faculty portrait. Missing assets show a clear fallback and do not prevent the offline course or developer section from opening. Use only media/images you have permission to distribute.

FACULTY DISPLAY
---------------
The DEVELOPED BY window shows each developer portrait, name, then registration number: Sabyasaachi Pradhan — 25BCE1914; Subhashish Roy — 25BCE5327. The faculty section shows `assets/fac.jpg` beside Dr. Swaminathan A, with `DBMS` directly beneath the name. If `assets/fac.jpg` is absent, the UI displays a fallback avatar and tells you the path to add. Edit `FACULTY_NAME`, `FACULTY_LABEL`, `FACULTY_PHOTO`, `DEVELOPER_NAMES`, and `DEVELOPER_REGISTRATION_NUMBERS` near the top of `feature_windows.py` to change these values.

SOURCE FILE MAP
---------------
app.py                       Main PySide6 application, navigation, themes and exports
database_view.py              Database Explorer
learning_content.py            Offline course, rule summaries, canonical quiz bank
feature_windows.py             LEARN / HELP / QUIZ / COMPETITIVE EXAM / DEVELOPED BY windows
quiz_engine.py                 Randomized attempts, answer validation and scoring
export_utils.py                CSV/history/report export functions
linter/rules.py                SQL001-SQL015 rule implementations
analyzer/performance_rules.py   P001-P022 performance-rule implementations
QRYVANTA.spec                  PyInstaller packaging configuration
QRYVANTA-Setup.iss             Inno Setup offline installer configuration
compile_installer.bat          Compile the Windows installer after PyInstaller succeeds
GITHUB_PUBLISHING.md           Safe guide for publishing the source repository

BUILD FROM SOURCE
-----------------
A standalone, copyable checklist is also provided in BUILD_INSTRUCTIONS.txt.

1. Install Python 3.11+ (use a compatible interpreter for your database drivers).
2. Create and activate a virtual environment.
3. Install dependencies: python -m pip install -r requirements.txt
4. Run from the project root: python main.py
5. Tests: python -m unittest discover -s tests -v
6. Build the onedir app: `python -m PyInstaller --clean --noconfirm QRYVANTA.spec`
7. On Windows with Inno Setup 6 installed, run `compile_installer.bat` (or compile `QRYVANTA-Setup.iss` directly).
8. The offline installer is written to `installer-output\QRYVANTA-Setup-1.1.0-Offline-x64.exe`.
9. See `GITHUB_PUBLISHING.md` for safe instructions to push this source tree to your own GitHub repository.

The target Windows PC does not need Python or internet access for the app's offline learning, help, quiz, exam practice and export features. Live database use still requires access to the selected database service. Oracle's console requires an installed compatible SQL*Plus client; QRYVANTA does not bundle Oracle client software or database credentials. ReportLab and python-docx are packaged by PyInstaller for PDF/DOCX exports. The source-only project intentionally excludes local .env files, credentials and prebuilt installer binaries. The Inno Setup script creates a per-user install by default and includes the offline study documents.

STUDY DOCUMENTS
---------------
docs/SQL_Linting_Performance_Study_Guide.docx and .pdf contain the offline course and current rule explanations. docs/QRYVANTA_Quiz_Questions_Answers.pdf is the answer/explanation edition generated from the canonical quiz bank. docs/Competitive_SQL_Practice_Questions.docx and docs/Competitive_SQL_Practice_Solutions.docx are matching questions-only and solution documents. To regenerate all five documents (including the study-guide PDF without LibreOffice), run: python tools/generate_study_documents.py

CREDIBLE REFERENCES
-------------------
SQLGlot: https://sqlglot.com/
PostgreSQL EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
Oracle Database documentation: https://docs.oracle.com/en/database/oracle/
MySQL EXPLAIN: https://dev.mysql.com/doc/refman/8.4/en/explain.html
SQLite Query Planner: https://www.sqlite.org/queryplanner.html
OWASP SQL Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

SECURITY NOTE
-------------
Do not include .env, database passwords, personal credential-store data, connection profile files, or local databases in any ZIP, installer or study document. Check SQL history and processing reports before sharing because SQL text and result metadata can contain private business information.


DEVELOPED BY layout refinement
The developer portrait cards reserve equal portrait/status slots so the names and registration numbers stay aligned whether both images are present or not. The faculty portrait and the name/DBMS text form a compact horizontally centered row and are vertically centered together. Add the approved portraits at assets/Dev1.jpg, assets/Dev2.jpg, and assets/fac.jpg before rebuilding to include them in the offline installer.
