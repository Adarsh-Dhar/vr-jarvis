# vr-jarvis

## Repository browser

The spatial VR workspace opens on a repository picker. Select a repository to open its folder tree, select folders to navigate, and select a file to inspect it in the code panel. Use **BACK** to move up one directory, **ROOT** to return to the repository root, and the page controls to browse long lists.

The code panel is currently **read-only**: it shows source with line numbers and page controls; editing and saving files are not implemented yet.

The server reads direct child folders of the project-root `repository/` directory by default. Override this with `JARVIS_REPOSITORY_DIR`.

## Run the real repository browser

From the project root, install the Python dependencies and start the server:

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="<your-key>"
uvicorn server.jarvis_server:app --host 0.0.0.0 --port 8000
```

In Unity, open the `ui/` project, choose **JARVIS → Use real server**, then enter Play mode. The `ui/ProjectSettings` configuration enables both legacy and new input handling.

For the Unity Editor, aim at a button with the pointer and click in the Game view. On Quest, point with tracked hands and pinch the index finger, or aim a Touch controller and press its trigger. Normal buttons activate on press-down; deliberate hold actions still require their configured hold time. A successful click is written to the Unity Console as `JARVIS input: clicked ...`.

When running on Quest, `127.0.0.1` refers to the headset. Set the `jarvis.server` PlayerPrefs value to the PC's LAN address (for example, `http://192.168.1.20:8000`) so the headset can reach the backend.

## Mock UI mode

Choose **JARVIS → Use mock data** to test the repository list, folders, file viewer, and button interaction without starting the backend. The mock contains a single sample repository.
