from __future__ import annotations

import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


try:
    import cv2  # type: ignore # noqa: F401
except ModuleNotFoundError:
    class _FakeCapture:
        def isOpened(self) -> bool:
            return False

        def read(self):
            return False, None

        def release(self) -> None:
            return None

    class _FakeCascade:
        def __init__(self, _path: str) -> None:
            self._path = _path

        def empty(self) -> bool:
            return True

        def detectMultiScale(self, *_args, **_kwargs):
            return []

    cv2_stub = types.SimpleNamespace(
        FONT_HERSHEY_SIMPLEX=0,
        LINE_AA=16,
        COLOR_BGR2RGB=0,
        COLOR_BGR2GRAY=0,
        data=types.SimpleNamespace(haarcascades=""),
        VideoCapture=lambda *_args, **_kwargs: _FakeCapture(),
        CascadeClassifier=lambda path: _FakeCascade(path),
        cvtColor=lambda frame, _code: frame,
        imencode=lambda _ext, _img: (False, None),
        circle=lambda *_args, **_kwargs: None,
        rectangle=lambda *_args, **_kwargs: None,
        putText=lambda *_args, **_kwargs: None,
        imshow=lambda *_args, **_kwargs: None,
        waitKey=lambda _ms: -1,
        destroyAllWindows=lambda: None,
    )
    sys.modules["cv2"] = cv2_stub
