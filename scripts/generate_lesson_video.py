#!/usr/bin/env python3
"""Generate one lesson's Gemini Notebook video from a terminal, no running backend/LLM needed.

This is a thin CLI wrapper around `app.services.lesson_video` — the same code the app's own
"Generate Gemini Notebook video" button (on the lesson page) calls, so the terminal and in-app paths always behave
identically and stay in sync.

Requires: `uv sync --group notebooklm` then `uv run notebooklm login` once.
Gemini Notebook's free tier caps video generation to a handful per day — run this per lesson,
at your own pace, not in a loop over every lesson.

Usage:
  uv run python scripts/generate_lesson_video.py github-actions --objective 1.1
  uv run python scripts/generate_lesson_video.py github-actions --slug founding-myths
  uv run python scripts/generate_lesson_video.py github-actions --objective 1.1 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.lesson_video import (
    PLACEHOLDER_RE,
    LessonVideoError,
    find_lesson_path,
    find_lesson_slug_by_objective,
    generate_lesson_video,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("topic_slug")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--objective",
        help="Objective code, e.g. 1.1 (its lessons dir must have one file)",
    )
    group.add_argument("--slug", help="Lesson file slug (basename without .md)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan, do nothing"
    )
    args = parser.parse_args()

    try:
        lesson_slug = args.slug or find_lesson_slug_by_objective(
            args.topic_slug, args.objective
        )
        lesson_path = find_lesson_path(args.topic_slug, lesson_slug)
        match = PLACEHOLDER_RE.search(lesson_path.read_text(encoding="utf-8"))
        if not match:
            print(
                f"{lesson_path} has no placeholder — video already set. Nothing to do."
            )
            return

        if args.dry_run:
            print(
                f"Would generate+download a video for {lesson_path} (source: {match.group('doc')})"
            )
            return

        video_path = generate_lesson_video(args.topic_slug, lesson_slug)
        print(
            f"Done — {lesson_path} now links to /media/{args.topic_slug}/{lesson_slug}.mp4"
        )
        print(f"(file on disk: {video_path})")
    except LessonVideoError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
