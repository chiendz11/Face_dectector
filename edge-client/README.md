# Edge Client

Local kiosk client for camera-based face verification at the edge.

## Layout

```text
edge-client/
  main.py                  # local compatibility launcher
  pyproject.toml           # package metadata and CLI entrypoint
  src/edge_client/
    app.py                 # runtime orchestration
    config.py              # environment configuration
    clients/backend.py     # backend API client
    hardware/camera.py     # camera adapter
    hardware/door.py       # door/relay adapter placeholder
    vision/face_detector.py
    ui/web_kiosk.py        # FastAPI local web kiosk
    ui/opencv_display.py   # legacy OpenCV window UI
    ui/static/kiosk.css    # web kiosk stylesheet
  tests/
```

## Entrypoints

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m edge_client
```

The Docker image installs the package and runs the `edge-client` console script.
