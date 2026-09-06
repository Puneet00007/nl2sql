-- Sample schema + data used to produce the README screenshots and for
-- quick local testing. Load it into a throwaway SQLite file:
--   sqlite3 examples/demo.db < examples/demo_schema.sql

CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT,
    department_id INTEGER,
    salary REAL,
    hire_date TEXT,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    city TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount REAL,
    order_date TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Sales'), (3, 'Marketing');

INSERT INTO employees VALUES
    (1, 'Asha Rao', 1, 95000, '2021-03-15'),
    (2, 'Vikram Singh', 1, 105000, '2019-07-01'),
    (3, 'Priya Menon', 2, 72000, '2020-11-20'),
    (4, 'Karthik Iyer', 2, 68000, '2022-01-10'),
    (5, 'Deepa Nair', 3, 61000, '2023-05-05');

INSERT INTO customers VALUES
    (1, 'Global Traders', 'Chennai'),
    (2, 'Bright Retail', 'Mumbai'),
    (3, 'North Star Co', 'Delhi');

INSERT INTO orders VALUES
    (1, 1, 15400, '2024-01-05'),
    (2, 1, 8200, '2024-01-06'),
    (3, 2, 22000, '2024-02-11'),
    (4, 3, 5400, '2024-02-20');
