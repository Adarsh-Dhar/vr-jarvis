# Security Challenge Fixture

This fixture contains intentional security vulnerabilities and hardcoded secrets for testing security scanning tools.

## Purpose
To validate that security tools correctly detect:
- Hardcoded secrets (API keys, passwords, credentials)
- SQL injection vulnerabilities
- XSS vulnerabilities
- Command injection vulnerabilities
- Weak encryption implementations

## Files

### config.py
Contains hardcoded secrets:
- API key (sk-...)
- Database URL with password
- AWS secret key

### vulnerable_app.py
Contains security vulnerabilities:
- SQL injection in `get_user()`
- XSS in `render_user_input()`
- Hardcoded password in `authenticate()`
- Command injection in `execute_command()`
- Weak encryption in `encrypt_data()`

### ground-truth.yaml
Contains the expected detection results:
- All secrets with locations and patterns
- All vulnerabilities with severity levels
- Function definitions

## Usage
Use this fixture to test:
- `scan_secrets` - should detect 3 secrets
- `scan_vulnerabilities` - should detect 5 vulnerabilities
- `verify_security` - should report security issues

## Note
This fixture is for testing purposes only. Do not use these patterns in production code.
