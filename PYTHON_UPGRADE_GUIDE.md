# Python Version Upgrade Guide

## Current Situation

**Current Python Version**: 3.9.6
**Required Python Version**: 3.10 or higher

### Why Upgrade is Needed

1. **MCP (Model Context Protocol)**: Requires Python 3.10+
   - Error message: "MCP requires Python 3.10 or above. Please upgrade your Python version in order to use it."

2. **Google Cloud Dependencies**: Require Python 3.11+ for full support
   - Warnings from google-auth, google.api_core, and other Google packages
   - FutureWarning: "You are using a non-supported Python version (3.9.6)"

3. **Security**: Python 3.9 reached end-of-life (October 2025)
   - No more security updates
   - Missing recent bug fixes and performance improvements

## Upgrade Options

### Option 1: Use pyenv (Recommended for macOS)

pyenv allows you to install and switch between multiple Python versions without affecting the system Python.

#### Installation

```bash
# Install pyenv using Homebrew
brew install pyenv

# Add pyenv to shell configuration
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# Reload shell
source ~/.zshrc
```

#### Install Python 3.11

```bash
# Install Python 3.11 (latest stable)
pyenv install 3.11.9

# Set as global default
pyenv global 3.11.9

# Verify
python --version
# Should output: Python 3.11.9
```

#### Set for This Project Only

```bash
cd /Users/adarsh/Documents/vr-agent
pyenv local 3.11.9
```

This creates a `.python-version` file in the project root, ensuring Python 3.11 is used for this project only.

### Option 2: Use Homebrew Python

```bash
# Install Python 3.11 via Homebrew
brew install python@3.11

# Create a virtual environment with Python 3.11
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify
python --version
```

### Option 3: Use conda/anaconda

If you already use conda:

```bash
# Create a new environment with Python 3.11
conda create -n jarvis python=3.11

# Activate
conda activate jarvis

# Verify
python --version
```

## Post-Upgrade Steps

### 1. Recreate Virtual Environment

```bash
# Remove old venv if it exists
rm -rf venv

# Create new venv with Python 3.11
python3.11 -m venv venv

# Activate
source venv/bin/activate
```

### 2. Reinstall Dependencies

```bash
# If requirements.txt exists
pip install -r requirements.txt

# Or if setup.py/pyproject.toml exists
pip install -e .
```

### 3. Verify Installation

```bash
# Test imports
python -c "import google.adk; print('ADK OK')"
python -c "import mcp; print('MCP OK')"

# Run agent import test
python test_agent_imports.py

# Run server import test
python test_server_import.py
```

### 4. Run Existing Tests

```bash
# Run the test suite
cd jarvis-tests
python -m pytest tests/ -v
```

## Expected Changes After Upgrade

### Warnings That Should Disappear

- ✅ "You are using a Python version 3.9 past its end of life"
- ✅ "MCP requires Python 3.10 or above"
- ✅ "You are using a non-supported Python version (3.9.6)"

### New Features Available

- Pattern matching (match/case statements)
- Improved error messages
- Better type hinting support
- Performance improvements

### Dependencies to Check

After upgrade, verify these packages work correctly:

- `google-adk`
- `google-genai`
- `google-cloud-*` packages
- `mcp` (if using MCP)
- `fastapi`
- `uvicorn`

## Rollback Plan

If issues arise after upgrade:

```bash
# Deactivate venv
deactivate

# Recreate with Python 3.9
python3.9 -m venv venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Compatibility Notes

### Code Changes Required

None expected. Python 3.11 is backward compatible with 3.9 for most code. However:

- Check for deprecated imports in third-party packages
- Verify async/await code still works
- Test type annotations if using heavy typing

### Tool Impact

- pytest: Should work without changes
- pip: Should work without changes
- uvicorn: Should work without changes
- FastAPI: Should work without changes

## Timeline Estimate

- **Installation**: 15-30 minutes
- **Dependency reinstallation**: 10-20 minutes
- **Verification testing**: 15-30 minutes
- **Total**: 40-80 minutes

## Risk Assessment

**Low Risk**:
- Python 3.11 is stable and widely used
- Most dependencies support 3.11
- Upgrade is straightforward with pyenv/venv

**Mitigation**:
- Keep old venv as backup
- Test in isolated environment first
- Rollback plan documented above

## Recommended Action

**Upgrade to Python 3.11.9 using pyenv local** for this project only. This:

- Doesn't affect system Python
- Provides project isolation
- Easy to switch back if needed
- Future-proofs the project

## Commands Summary

```bash
# Install pyenv (if not already installed)
brew install pyenv

# Add to shell (one-time)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Install Python 3.11
pyenv install 3.11.9

# Set for this project
cd /Users/adarsh/Documents/vr-agent
pyenv local 3.11.9

# Recreate venv
rm -rf venv
python -m venv venv
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt  # or equivalent

# Verify
python --version
python test_agent_imports.py
python test_server_import.py
```
