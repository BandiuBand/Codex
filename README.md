# Codex Agent Framework

This repository contains a small agent execution framework and demo agents. Before running any demos, ensure Python dependencies are installed:

```bash
pip install -r requirements.txt
```

To verify the demos run end-to-end, execute one of the entry points below from the repository root:

```bash
# Start the web editor (default command)
python run.py

# Run the web editor on a different host/port
python run.py web --host 127.0.0.1 --port 8000

# Run the bundled demo agents sequentially
python run.py demo

# Run backend + frontend integration tests
python run.py test
```

If you see `ModuleNotFoundError: No module named 'yaml'`, it means the `PyYAML` dependency has not been installed; running the install command above resolves it.

## Web graph editor

The project includes a lightweight web UI for assembling agent graphs on a canvas and exporting them to YAML definitions compatible with the existing loader.

1. Start the server:

   ```bash
   python -m agentfw.web --host 127.0.0.1 --port 8000
   ```

   The service persists agent definitions in the `agents/` directory by default (override with `AGENTFW_AGENTS_DIR`).

2. Open the editor in your browser at http://127.0.0.1:8000/.

From the UI you can add steps, link transitions, set `entry_step_id` and `end_step_ids`, import/export JSON, validate transitions, and save agents back to YAML files on disk.
