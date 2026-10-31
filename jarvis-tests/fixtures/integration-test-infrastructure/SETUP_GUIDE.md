# Integration Test Infrastructure Setup Guide

This document describes the integration test infrastructure for Layer 3 tests.

## Components

### 1. Database Fixtures
**Location**: `databases/`

- **test.db**: SQLite database with test data
  - Tables: users, posts, comments
  - Pre-populated with sample data
  - Used for testing database-related tools

**Tools that use this**:
- inspect_database_schema
- inspect_tables
- inspect_columns
- analyze_database_queries
- trace_database_operation

### 2. API Fixtures
**Location**: `apis/`

- **simple_flask_api.py**: Flask REST API server
  - Endpoints: /, /health, /api/users, /api/posts
  - CRUD operations for users and posts
  - Runs on port 5001

- **openapi.yaml**: OpenAPI 3.0 specification
  - Describes the Flask API
  - Used for testing API schema inspection

**Tools that use this**:
- discover_api_endpoints
- inspect_api_schema
- analyze_api_contract
- trace_api_call
- inspect_http_routes

### 3. Git Repositories
**Location**: `git-repos/`

- **simple-repo**: Git repository with multiple branches
  - Main branch: 3 commits
  - Feature branch: 1 additional commit
  - Used for testing git-related tools

**Tools that use this**:
- get_diff
- trace_file_history
- find_introducing_commit
- create_worktree
- get_branch_info

### 4. Runtime Fixtures
**Location**: `runtime/`

- **sample_app.py**: Synchronous Python application
  - Classes, functions, recursion, sorting
  - Used for runtime tracing and profiling

- **sample_async_app.py**: Asynchronous Python application
  - Async/await, concurrent execution
  - Worker pool pattern
  - Used for async runtime testing

**Tools that use this**:
- collect_execution_trace
- record_function_calls
- attach_runtime_profiler
- capture_application_logs

## Usage

### Starting the Flask API Server
```bash
cd /path/to/jarvis-tests/fixtures/integration-test-infrastructure
python3 apis/simple_flask_api.py
```

The server will start on http://localhost:5001

### Running Runtime Applications
```bash
# Synchronous app
python3 runtime/sample_app.py

# Async app
python3 runtime/sample_async_app.py
```

### Accessing the Database
```bash
sqlite3 databases/test.db
sqlite> .tables
sqlite> SELECT * FROM users;
```

### Working with Git Repository
```bash
cd git-repos/simple-repo
git log --oneline
git branch -a
git diff main feature/new-feature
```

## Running Setup Script

The setup script (`setup.sh`) initializes all infrastructure:

```bash
cd /path/to/jarvis-tests/fixtures/integration-test-infrastructure
./setup.sh
```

This will:
- Create the SQLite database
- Initialize the git repository
- Make Python scripts executable

## Integration Test Structure

Integration tests should reference these fixtures in their test specifications:

```yaml
fixture:
  type: database
  path: integration-test-infrastructure/databases/test.db

fixture:
  type: api
  path: integration-test-infrastructure/apis/simple_flask_api.py
  url: http://localhost:5001

fixture:
  type: git
  path: integration-test-infrastructure/git-repos/simple-repo

fixture:
  type: runtime
  path: integration-test-infrastructure/runtime/sample_app.py
```

## Maintenance

- To reset the database: Delete `test.db` and run setup.sh
- To reset git repo: Delete `simple-repo/.git` and run setup.sh
- To update API: Modify `simple_flask_api.py` and restart server
- To update runtime apps: Modify Python files directly
