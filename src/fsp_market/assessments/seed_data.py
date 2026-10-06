"""Backend / Python Core Assessment seed data (pure data; loaded by seed.py).

Bonsai-generated, controller-reviewed: every question has exactly one correct option."""

SPECIALIZATION = {"code": "backend_python", "name": "Backend / Python"}

COMPETENCIES = [
    {"code": "python", "name": "Python"},
    {"code": "sql", "name": "SQL"},
    {"code": "api_fastapi", "name": "FastAPI"},
    {"code": "testing", "name": "Testing"},
    {"code": "docker_basics", "name": "Docker Basics"},
    {"code": "system_thinking", "name": "System Thinking"},
]

FAMILIES = [
    {
        "allowed_formats": ["DETERMINISTIC_QUESTION", "CODE_READING"],
        "code": "backend.python.junior.core_types",
        "competency": "python",
        "difficulty_band": 2,
        "edge_case_classes": ["int", "float", "str"],
        "presets": [
            {
                "code": "backend.python.junior.core_types.t1.p1",
                "parameters": {
                    "correct": "B",
                    "dimension": "type_conversion",
                    "options": {
                        "A": "<class 'int'>",
                        "B": "<class 'float'>",
                        "C": "<class 'str'>",
                        "D": "<class 'bool'>",
                    },
                    "snippet": "x = 5\ny = x + 3.0\nprint(type(y))",
                },
            },
            {
                "code": "backend.python.junior.core_types.t1.p2",
                "parameters": {
                    "correct": "B",
                    "dimension": "type_identity",
                    "options": {"A": "1", "B": "2", "C": "True", "D": "TypeError"},
                    "snippet": "a = True\nb = a + 1\nprint(b)",
                },
            },
        ],
        "rubric": [
            {"dimension": "type_identity", "weight": 0.5},
            {"dimension": "type_conversion", "weight": 0.5},
        ],
        "target_grade": "JUNIOR",
        "template": {
            "code": "backend.python.junior.core_types.t1",
            "parameter_schema": {"snippet": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "Consider the following Python snippet:\n"
            "{snippet}\n"
            "What is the output of the final print statement?",
            "task_format": "CODE_READING",
        },
    },
    {
        "allowed_formats": ["CODE_READING", "DETERMINISTIC_QUESTION"],
        "code": "backend.python.middle.code_reading",
        "competency": "python",
        "difficulty_band": 3,
        "edge_case_classes": ["list", "dict", "tuple"],
        "presets": [
            {
                "code": "backend.python.middle.code_reading.t1.p1",
                "parameters": {
                    "correct": "B",
                    "dimension": "control_flow",
                    "expr": "items[1]",
                    "options": {"A": "2", "B": "20", "C": "4", "D": "40"},
                    "snippet": "items = [1, 2, 3, 4]\n"
                    "for i in range(len(items)):\n"
                    "    if items[i] % 2 == 0:\n"
                    "        items[i] = items[i] * 10",
                },
            },
            {
                "code": "backend.python.middle.code_reading.t1.p2",
                "parameters": {
                    "correct": "C",
                    "dimension": "data_structure",
                    "expr": "data['c']",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "None"},
                    "snippet": "data = {'a': 1, 'b': 2}\ndata['c'] = data['a'] + data['b']",
                },
            },
        ],
        "rubric": [
            {"dimension": "control_flow", "weight": 0.4},
            {"dimension": "data_structure", "weight": 0.3},
            {"dimension": "side_effect", "weight": 0.3},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.python.middle.code_reading.t1",
            "parameter_schema": {"expr": "str", "snippet": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "What is the final value of the variable `result` after executing the "
            "following code?\n"
            "{snippet}\n"
            "result = {expr}",
            "task_format": "CODE_READING",
        },
    },
    {
        "allowed_formats": ["SQL_REASONING", "DETERMINISTIC_QUESTION"],
        "code": "backend.sql.junior.select_filter",
        "competency": "sql",
        "difficulty_band": 2,
        "edge_case_classes": ["WHERE", "AND", "OR"],
        "presets": [
            {
                "code": "backend.sql.junior.select_filter.t1.p1",
                "parameters": {
                    "columns": "id, name, age, city",
                    "condition": "age > 25 AND city = 'Berlin'",
                    "correct": "A",
                    "dimension": "filter_logic",
                    "options": {
                        "A": "SELECT * FROM users WHERE age > 25 AND city = 'Berlin'",
                        "B": "SELECT * FROM users WHERE age < 25 AND city = 'Berlin'",
                        "C": "SELECT * FROM users WHERE age > 25 OR city = 'Berlin'",
                        "D": "SELECT * FROM users WHERE age = 25 AND city = 'Berlin'",
                    },
                    "table": "users",
                },
            },
            {
                "code": "backend.sql.junior.select_filter.t1.p2",
                "parameters": {
                    "columns": "id, customer_id, amount, status",
                    "condition": "status = 'shipped' AND amount >= 100",
                    "correct": "A",
                    "dimension": "filter_logic",
                    "options": {
                        "A": "SELECT * FROM orders WHERE status = 'shipped' AND amount >= 100",
                        "B": "SELECT * FROM orders WHERE status = 'shipped' OR amount >= 100",
                        "C": "SELECT * FROM orders WHERE status != 'shipped' AND amount >= 100",
                        "D": "SELECT * FROM orders WHERE status = 'shipped' AND amount < 100",
                    },
                    "table": "orders",
                },
            },
        ],
        "rubric": [
            {"dimension": "filter_logic", "weight": 0.6},
            {"dimension": "column_selection", "weight": 0.4},
        ],
        "target_grade": "JUNIOR",
        "template": {
            "code": "backend.sql.junior.select_filter.t1",
            "parameter_schema": {"columns": "str", "condition": "str", "table": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "Given the table `{table}` with columns `{columns}`, which SQL query "
            "returns all rows where `{condition}`?",
            "task_format": "SQL_REASONING",
        },
    },
    {
        "allowed_formats": ["SQL_REASONING", "DETERMINISTIC_QUESTION"],
        "code": "backend.sql.middle.joins_aggregation",
        "competency": "sql",
        "difficulty_band": 3,
        "edge_case_classes": ["JOIN", "GROUP BY", "HAVING"],
        "presets": [
            {
                "code": "backend.sql.middle.joins_aggregation.t1.p1",
                "parameters": {
                    "correct": "A",
                    "dim": "customers",
                    "dimension": "aggregation",
                    "fact": "orders",
                    "group_col": "customer_id",
                    "join_col": "customer_id",
                    "join_table": "customers",
                    "key": "customer_id",
                    "options": {
                        "A": "SELECT f.customer_id, SUM(f.amount) FROM orders f "
                        "JOIN customers d ON f.customer_id = d.id GROUP BY "
                        "f.customer_id",
                        "B": "SELECT f.customer_id, COUNT(f.amount) FROM orders "
                        "f JOIN customers d ON f.customer_id = d.id GROUP "
                        "BY f.customer_id",
                        "C": "SELECT f.customer_id, SUM(f.amount) FROM orders f "
                        "JOIN customers d ON f.customer_id = d.id",
                        "D": "SELECT f.customer_id, SUM(f.amount) FROM orders f "
                        "JOIN customers d ON f.customer_id = d.id WHERE "
                        "SUM(f.amount) > 0 GROUP BY f.customer_id",
                    },
                    "table": "orders",
                },
            },
            {
                "code": "backend.sql.middle.joins_aggregation.t1.p2",
                "parameters": {
                    "correct": "A",
                    "dim": "products",
                    "dimension": "aggregation",
                    "fact": "sales",
                    "group_col": "product_id",
                    "join_col": "product_id",
                    "join_table": "products",
                    "key": "product_id",
                    "options": {
                        "A": "SELECT f.product_id, SUM(f.amount) FROM sales f "
                        "JOIN products d ON f.product_id = d.id GROUP BY "
                        "f.product_id",
                        "B": "SELECT f.product_id, COUNT(f.amount) FROM sales f "
                        "JOIN products d ON f.product_id = d.id GROUP BY "
                        "f.product_id",
                        "C": "SELECT f.product_id, SUM(f.amount) FROM sales f "
                        "JOIN products d ON f.product_id = d.id",
                        "D": "SELECT f.product_id, SUM(f.amount) FROM sales f "
                        "JOIN products d ON f.product_id = d.id WHERE "
                        "SUM(f.amount) > 0 GROUP BY f.product_id",
                    },
                    "table": "sales",
                },
            },
        ],
        "rubric": [
            {"dimension": "join_type", "weight": 0.4},
            {"dimension": "aggregation", "weight": 0.3},
            {"dimension": "grouping", "weight": 0.3},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.sql.middle.joins_aggregation.t1",
            "parameter_schema": {"dim": "str", "fact": "str", "key": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "Table `{fact}`({key}, amount) and table `{dim}`(id, name). Which "
            "query returns the total `amount` per `{key}`, counting only rows that "
            "have a matching `{dim}` row?",
            "task_format": "SQL_REASONING",
        },
    },
    {
        "allowed_formats": ["API_REASONING", "DETERMINISTIC_QUESTION"],
        "code": "backend.api.middle.api_validation",
        "competency": "api_fastapi",
        "difficulty_band": 3,
        "edge_case_classes": ["422", "400", "404"],
        "presets": [
            {
                "code": "backend.api.middle.api_validation.t1.p1",
                "anchor": True,
                "parameters": {
                    "correct": "C",
                    "dimension": "validation_error",
                    "endpoint": "POST /orders",
                    "fields": "quantity (1-50), price (>0), discount (0-30)",
                    "invalid_value": "quantity = 51",
                    "options": {
                        "A": "200 OK",
                        "B": "400 Bad Request",
                        "C": "422 Unprocessable Entity",
                        "D": "500 Internal Server Error",
                    },
                },
            },
            {
                "code": "backend.api.middle.api_validation.t1.p2",
                "parameters": {
                    "correct": "C",
                    "dimension": "status_code",
                    "endpoint": "POST /subscriptions",
                    "fields": "users (1-100), months (1-24), trial (0-14)",
                    "invalid_value": "trial = 15",
                    "options": {
                        "A": "200 OK",
                        "B": "400 Bad Request",
                        "C": "422 Unprocessable Entity",
                        "D": "404 Not Found",
                    },
                },
            },
        ],
        "rubric": [
            {"dimension": "validation_error", "weight": 0.5},
            {"dimension": "status_code", "weight": 0.5},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.api.middle.api_validation.t1",
            "parameter_schema": {"endpoint": "str", "fields": "str", "invalid_value": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "A FastAPI endpoint `{endpoint}` validates `{fields}`. What HTTP "
            "status code is returned when `{invalid_value}` is provided?",
            "task_format": "API_REASONING",
        },
    },
    {
        "allowed_formats": ["RUBRIC_CHECK", "DETERMINISTIC_QUESTION"],
        "code": "backend.testing.middle.edge_cases",
        "competency": "testing",
        "difficulty_band": 3,
        "edge_case_classes": ["empty_input", "boundary_value", "null_value"],
        "presets": [
            {
                "code": "backend.testing.middle.edge_cases.t1.p1",
                "parameters": {
                    "correct": "A",
                    "dimension": "edge_case_identification",
                    "function_name": "calculate_average",
                    "input_type": "a list of numbers",
                    "options": {
                        "A": "average([]) raises ZeroDivisionError or a defined error",
                        "B": "average([1, 2, 3]) == 2",
                        "C": "average([-1, -2]) == -1.5",
                        "D": "average([5]) == 5",
                    },
                    "signature": "def average(xs: list[float]) -> float  # returns sum(xs)/len(xs)",
                    "tests": "test_average_of_three_numbers\n"
                    "test_average_of_single_element\n"
                    "test_average_with_negative_numbers",
                },
            },
            {
                "code": "backend.testing.middle.edge_cases.t1.p2",
                "parameters": {
                    "correct": "C",
                    "dimension": "test_coverage",
                    "function_name": "parse_date",
                    "input_type": "a date string",
                    "options": {
                        "A": "parse_age('42') == 42",
                        "B": "parse_age('0') == 0",
                        "C": "parse_age('151') raises ValueError (upper boundary)",
                        "D": "parse_age('abc') raises ValueError",
                    },
                    "signature": "def parse_age(s: str) -> int  # '0'..'150' valid, "
                    "otherwise raises ValueError",
                    "tests": "test_parse_valid_age\ntest_parse_zero\ntest_parse_non_numeric_raises",
                },
            },
        ],
        "rubric": [
            {"dimension": "edge_case_identification", "weight": 0.5},
            {"dimension": "test_coverage", "weight": 0.5},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.testing.middle.edge_cases.t1",
            "parameter_schema": {"signature": "str", "tests": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "Function under test: {signature}\n"
            "Existing tests:\n"
            "{tests}\n"
            "Which missing test targets the most important uncovered edge case?",
            "task_format": "RUBRIC_CHECK",
        },
    },
    {
        "allowed_formats": ["DETERMINISTIC_QUESTION", "RUBRIC_CHECK"],
        "code": "backend.docker.middle.compose_basics",
        "competency": "docker_basics",
        "difficulty_band": 3,
        "edge_case_classes": ["depends_on", "ports", "volumes"],
        "presets": [
            {
                "code": "backend.docker.middle.compose_basics.t1.p1",
                "parameters": {
                    "correct": "B",
                    "dep": "db",
                    "dependency": "db",
                    "dimension": "service_dependency",
                    "options": {
                        "A": "depends_on: [db]",
                        "B": "depends_on: {db: {condition: service_healthy}}",
                        "C": "depends_on: {db: {condition: service_started}}",
                        "D": "links: [db]",
                    },
                    "service_name": "web",
                    "svc": "web",
                },
            },
            {
                "code": "backend.docker.middle.compose_basics.t1.p2",
                "parameters": {
                    "correct": "B",
                    "dep": "cache",
                    "dependency": "cache",
                    "dimension": "service_dependency",
                    "options": {
                        "A": "depends_on: [cache]",
                        "B": "depends_on: {cache: {condition: service_healthy}}",
                        "C": "depends_on: {cache: {condition: service_started}}",
                        "D": "links: [cache]",
                    },
                    "service_name": "api",
                    "svc": "api",
                },
            },
        ],
        "rubric": [
            {"dimension": "service_dependency", "weight": 0.4},
            {"dimension": "port_mapping", "weight": 0.3},
            {"dimension": "volume_mount", "weight": 0.3},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.docker.middle.compose_basics.t1",
            "parameter_schema": {"dep": "str", "svc": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "In docker-compose, service `{svc}` must start only after `{dep}` "
            "reports a passing healthcheck. Which `depends_on` configuration does "
            "this?",
            "task_format": "DETERMINISTIC_QUESTION",
        },
    },
    {
        "allowed_formats": ["RUBRIC_CHECK", "DETERMINISTIC_QUESTION"],
        "code": "backend.system.middle.tradeoffs",
        "competency": "system_thinking",
        "difficulty_band": 4,
        "edge_case_classes": ["latency", "throughput", "consistency"],
        "presets": [
            {
                "code": "backend.system.middle.tradeoffs.t1.p1",
                "parameters": {
                    "correct": "B",
                    "dimension": "tradeoff_analysis",
                    "load": "10,000 orders per minute",
                    "options": {
                        "A": "Synchronous processing with a single database",
                        "B": "Asynchronous processing with a message queue",
                        "C": "Synchronous processing with a read replica",
                        "D": "Asynchronous processing with a single database",
                    },
                    "priority": "throughput",
                    "scenario": "e-commerce order processing",
                },
            },
            {
                "code": "backend.system.middle.tradeoffs.t1.p2",
                "parameters": {
                    "correct": "B",
                    "dimension": "consistency",
                    "load": "1,000 updates per second",
                    "options": {
                        "A": "Eventual consistency with a cache",
                        "B": "Strong consistency with a single database",
                        "C": "Eventual consistency with a message queue",
                        "D": "Strong consistency with a read replica",
                    },
                    "priority": "consistency",
                    "scenario": "user profile updates",
                },
            },
        ],
        "rubric": [
            {"dimension": "tradeoff_analysis", "weight": 0.5},
            {"dimension": "scalability", "weight": 0.3},
            {"dimension": "consistency", "weight": 0.2},
        ],
        "target_grade": "MIDDLE",
        "template": {
            "code": "backend.system.middle.tradeoffs.t1",
            "parameter_schema": {"load": "str", "priority": "str", "scenario": "str"},
            "scoring_rule": {"type": "choice"},
            "structure": "A system `{scenario}` must handle `{load}`. Which architectural "
            "choice best balances `{priority}`?",
            "task_format": "RUBRIC_CHECK",
        },
    },
]
