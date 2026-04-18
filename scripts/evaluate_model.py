from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

from sklearn.metrics import classification_report, f1_score, precision_score, recall_score

# Make backend importable from the repo root
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.deepface_service import DeepFaceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate face recognition model accuracy on a labeled dataset."
    )
    parser.add_argument(
        "--gallery-dir",
        required=True,
        help="Path to gallery images organized by label subfolder.",
    )
    parser.add_argument(
        "--query-dir",
        required=True,
        help="Path to query images organized by label subfolder.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Cosine similarity threshold for a positive match.",
    )
    parser.add_argument(
        "--model-name",
        default="VGG-Face",
        help="Model name to use for face embedding extraction.",
    )
    return parser.parse_args()


def load_labeled_images(base_dir: Path) -> dict[str, list[Path]]:
    gallery = {}
    for label_dir in sorted(base_dir.iterdir()):
        if not label_dir.is_dir():
            continue
        label = label_dir.name
        images = [
            path
            for path in sorted(label_dir.iterdir())
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if images:
            gallery[label] = images
    return gallery


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(l * r for l, r in zip(left, right))
    left_norm = math.sqrt(sum(l * l for l in left))
    right_norm = math.sqrt(sum(r * r for r in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def main() -> None:
    args = parse_args()
    gallery_dir = Path(args.gallery_dir)
    query_dir = Path(args.query_dir)

    if not gallery_dir.exists() or not gallery_dir.is_dir():
        raise SystemExit(f"Gallery directory not found: {gallery_dir}")
    if not query_dir.exists() or not query_dir.is_dir():
        raise SystemExit(f"Query directory not found: {query_dir}")

    dataset_name = "DeepFace"
    print(f"Evaluating face recognition accuracy with model: {dataset_name}")

    service = DeepFaceService()
    service.model_name = args.model_name

    gallery_images = load_labeled_images(gallery_dir)
    query_images = load_labeled_images(query_dir)

    if not gallery_images:
        raise SystemExit("No gallery images found.")
    if not query_images:
        raise SystemExit("No query images found.")

    print(f"Gallery labels: {len(gallery_images)}")
    print(f"Query labels: {len(query_images)}")

    gallery_embeddings: dict[str, list[list[float]]] = {}
    for label, paths in gallery_images.items():
        embeddings = []
        for image_path in paths:
            with image_path.open("rb") as image_file:
                embedding = service.embed_face(image_file.read())
                embeddings.append(embedding)
        gallery_embeddings[label] = embeddings

    y_true: list[str] = []
    y_pred: list[str] = []
    y_score: list[float] = []

    for label, paths in query_images.items():
        for image_path in paths:
            with image_path.open("rb") as image_file:
                query_embedding = service.embed_face(image_file.read())

            best_label = "unknown"
            best_score = -1.0
            for candidate_label, embeddings in gallery_embeddings.items():
                for gallery_embedding in embeddings:
                    score = cosine_similarity(query_embedding, gallery_embedding)
                    if score > best_score:
                        best_score = score
                        best_label = candidate_label

            if best_score < args.threshold:
                best_label = "unknown"

            y_true.append(label)
            y_pred.append(best_label)
            y_score.append(best_score)

    labels = sorted(set(y_true) | set(y_pred))
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))

    overall_precision = precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    overall_recall = recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    overall_f1 = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)

    print("Summary metrics:")
    print(f"  Precision: {overall_precision:.4f}")
    print(f"  Recall:    {overall_recall:.4f}")
    print(f"  F1 score:  {overall_f1:.4f}")
    print(f"  Threshold: {args.threshold}")


if __name__ == "__main__":
    main()
