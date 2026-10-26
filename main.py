import argparse
import json
import sys
from pathlib import Path
import config
from pipeline import leetcode, solver, scenes, render, thumbnail, metadata, youtube, notify


def run(
    dry_run: bool = False,
    force: bool = False,
    problem_id: int | None = None,
    advance: bool = False,
    lang: str | None = None,
    no_advance: bool = False,
):
    # Set runtime language if flag is passed.
    if lang:
        config.LANGUAGE = lang

    # Resolve problem ID.
    target_id = problem_id if problem_id is not None else leetcode.get_current_sequence_id()
    print("\n==========================================")
    print(f"  LeetCode Sequential Run: Problem #{target_id}")
    print(f"  Channel: {config.CHANNEL_NAME} | Lang: {config.LANGUAGE.upper()}")
    print("==========================================\n")

    # Fetch problem details.
    problem = leetcode.fetch_daily(target_id)
    print(f"Problem: #{problem['id']} {problem['title']} ({problem['difficulty']})")
    print(f"Topics: {', '.join(problem['topics'])}\n")

    # Keep English and Hindi/Hinglish assets in separate directories.
    suffix = f"_{config.LANGUAGE}" if config.LANGUAGE != "en" else ""
    work = config.DATA / f"{problem['id']}-{problem['slug']}{suffix}"
    work.mkdir(parents=True, exist_ok=True)

    done_flag = work / "done.txt"
    if done_flag.exists() and not force:
        print(f"Problem #{problem['id']} ({config.LANGUAGE.upper()}) was already processed. Use --force to regenerate.")
        return

    # Solve and verify; solution.json is cached per language directory.
    print(f"Loading/Generating Java solutions and {config.LANGUAGE.upper()} narration...")
    sol, results = solver.generate_verified(problem, work_dir=work)

    # Compile timeline and render video.
    print("\nCompiling 1080p slide timeline...")
    beats = scenes.build_beats(problem, sol, results)
    video_path, chapters = render.build_video(beats, problem, work, seed=int(problem["id"]))

    # Metadata and thumbnail are cached per language directory.
    print("\nGenerating metadata and thumbnail...")
    meta = metadata.build(problem, sol, work_dir=work)
    thumb_code = sol["approaches"][-1].get("java_code", sol["approaches"][-1]["code"])
    thumb_path = thumbnail.make(problem, meta, thumb_code, work / "thumb.jpg")

    meta["description"] = metadata.build_description(problem, sol, meta, chapters)
    (work / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✓ Video Generated: {video_path}")
    print(f"✓ Thumbnail Generated: {thumb_path}")

    # Dry-run or upload.
    if dry_run:
        print("\n[DRY RUN] Completed locally. Skipped YouTube upload.")
        if advance and not no_advance:
            leetcode.advance_sequence(int(problem["id"]))
        return

    print("\nPublishing to YouTube...")
    try:
        vid_id = youtube.upload(video_path, thumb_path, meta)
        print(f"✓ Uploaded successfully! Video ID: {vid_id}")
        done_flag.write_text(f"uploaded: {vid_id}\n", encoding="utf-8")
        notify.success(problem, vid_id)

        # Manual language runs pass --no-advance. The bilingual workflow advances
        # the sequence once, after both uploads succeed.
        if not no_advance:
            leetcode.advance_sequence(int(problem["id"]))
    except Exception as e:
        print(f"Upload failed: {e}")
        notify.failure(problem, e)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sequential LeetCode YouTube Automation")
    parser.add_argument("--dry-run", action="store_true", help="Generate video locally without uploading")
    parser.add_argument("--force", action="store_true", help="Force regenerate even if the problem/language was completed")
    parser.add_argument("--id", type=int, default=None, help="Specific problem ID (e.g. --id 1)")
    parser.add_argument("--advance", action="store_true", help="Advance sequence pointer during dry-run")
    parser.add_argument("--no-advance", action="store_true", help="Do not advance sequence after this run")
    parser.add_argument("--lang", type=str, default=None, choices=["en", "hi"], help="Language: en (English) or hi (Hindi/Hinglish)")

    args = parser.parse_args()
    try:
        run(
            dry_run=args.dry_run,
            force=args.force,
            problem_id=args.id,
            advance=args.advance,
            lang=args.lang,
            no_advance=args.no_advance,
        )
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)
