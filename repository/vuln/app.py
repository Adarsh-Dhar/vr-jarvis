from flask import Flask, request
import sqlite3
import subprocess

app = Flask(__name__)

# Hardcoded secrets (vulnerability #1)
AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
password = "supersecret123"

@app.route('/user')
def get_user():
    user_id = request.args.get("id")

    # SQL injection vulnerability - string concatenation (vulnerability #2)
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()

    return str(result)

@app.route('/user_safe')
def get_user_safe():
    user_id = request.args.get("id")

    # Parameterized query - safe (reference implementation)
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
    result = cursor.fetchall()
    conn.close()

    return str(result)

@app.route('/execute')
def execute_command():
    cmd = request.args.get("cmd")

    # Command injection vulnerability - shell=True (vulnerability #3)
    subprocess.call(cmd, shell=True)

    return "Command executed"

@app.route('/eval_code')
def eval_code():
    code = request.args.get("code")

    # Code injection vulnerability - eval() (vulnerability #4)
    result = eval(code)

    return str(result)

if __name__ == "__main__":
    app.run(debug=True)
