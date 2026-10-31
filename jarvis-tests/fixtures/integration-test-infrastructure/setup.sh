#!/bin/bash
# Setup script for integration test infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Setting up integration test infrastructure in $SCRIPT_DIR"

# Setup databases
echo "Setting up databases..."
DB_DIR="$SCRIPT_DIR/databases"
if [ ! -f "$DB_DIR/test.db" ]; then
    sqlite3 "$DB_DIR/test.db" < "$DB_DIR/init_test_db.sql"
    echo "Created SQLite test database"
else
    echo "SQLite test database already exists"
fi

# Setup git repositories
echo "Setting up git repositories..."
GIT_DIR="$SCRIPT_DIR/git-repos"
if [ ! -d "$GIT_DIR/simple-repo/.git" ]; then
    cd "$GIT_DIR/simple-repo"
    git init
    git config user.name "Test User"
    git config user.email "test@example.com"
    git add README.md
    git commit -m "Initial commit"
    git add main.py
    git commit -m "Add main.py with hello functions"
    git add main.py
    git commit -m "Add calculate_sum function"
    git checkout -b feature/new-feature
    git add feature.py
    git commit -m "Add feature.py with new functions"
    git checkout main
    cd "$SCRIPT_DIR"
    echo "Created simple git repository"
else
    echo "Git repository already exists"
fi

# Make Python scripts executable
echo "Making Python scripts executable..."
chmod +x "$SCRIPT_DIR/apis/simple_flask_api.py"
chmod +x "$SCRIPT_DIR/runtime/sample_app.py"
chmod +x "$SCRIPT_DIR/runtime/sample_async_app.py"

echo "Integration test infrastructure setup complete!"
echo ""
echo "Available components:"
echo "  - Database: $DB_DIR/test.db"
echo "  - Git repo: $GIT_DIR/simple-repo"
echo "  - Flask API: $SCRIPT_DIR/apis/simple_flask_api.py"
echo "  - Runtime apps: $SCRIPT_DIR/runtime/"
echo ""
echo "To start the Flask API server:"
echo "  python3 $SCRIPT_DIR/apis/simple_flask_api.py"
