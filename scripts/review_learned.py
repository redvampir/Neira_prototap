"""
CLI для обзора недавно изучённых источников: approve / reject
Сохраняет решения в data/learning_reviewed.json
Usage:
  python -m scripts.review_learned --list
  python -m scripts.review_learned --interactive
  python -m scripts.review_learned --approve 3
  python -m scripts.review_learned --reject 2 --reason "спам"

"""
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

HISTORY = Path("data/learning_history.json")
REVIEWED = Path("data/learning_reviewed.json")


def load_history() -> List[Dict[str, Any]]:
    if not HISTORY.exists():
        return []
    return json.loads(HISTORY.read_text(encoding='utf-8'))


def load_reviewed() -> Dict[str, Any]:
    if not REVIEWED.exists():
        return {}
    return json.loads(REVIEWED.read_text(encoding='utf-8'))


def save_reviewed(d: Dict[str, Any]):
    REVIEWED.parent.mkdir(parents=True, exist_ok=True)
    REVIEWED.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')


def list_unreviewed(history: List[Dict[str, Any]], reviewed: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for i, entry in enumerate(history):
        key = f"{entry.get('source')}|{entry.get('learned_at')}|{entry.get('title')}"
        if key not in reviewed:
            out.append({"index": i, "entry": entry, "key": key})
    return out


def interactive_review():
    history = load_history()
    reviewed = load_reviewed()
    todo = list_unreviewed(history, reviewed)
    if not todo:
        print("Нет непросмотренных записей.")
        return

    for item in todo:
        i = item["index"]
        e = item["entry"]
        print("-" * 60)
        print(f"Index: {i}")
        print(f"Title: {e.get('title')}")
        print(f"Source: {e.get('source')}")
        print(f"Category: {e.get('category')}")
        print(f"Words: {e.get('word_count')}")
        summary = e.get('summary')
        if summary:
            print("Summary:\n", summary)
        else:
            print("(нет summary)")
        print("-" * 60)
        ans = input("Approve this entry? [y/N] ").strip().lower()
        key = item["key"]
        reviewed[key] = {
            "approved": ans == 'y',
            "reviewed_at": datetime.now().isoformat(),
        }
        save_reviewed(reviewed)
        print(f"Saved: approved={reviewed[key]['approved']}\n")


def cmd_list():
    history = load_history()
    reviewed = load_reviewed()
    todo = list_unreviewed(history, reviewed)
    if not history:
        print("History empty or missing: data/learning_history.json")
        return

    print(f"Total entries: {len(history)} | Unreviewed: {len(todo)}")
    for i, e in enumerate(history[-50:]):
        idx = len(history) - 50 + i if len(history) > 50 else i
        approved = None
        key = f"{e.get('source')}|{e.get('learned_at')}|{e.get('title')}"
        if key in reviewed:
            approved = reviewed[key].get('approved')
        print(f"[{idx}] {e.get('title')} ({e.get('word_count')} words) - {e.get('category')} - reviewed={approved}")


def cmd_approve(index: int, reason: str | None = None):
    history = load_history()
    reviewed = load_reviewed()
    if index < 0 or index >= len(history):
        print("Index out of range")
        return
    e = history[index]
    key = f"{e.get('source')}|{e.get('learned_at')}|{e.get('title')}"
    reviewed[key] = {"approved": True, "reason": reason, "reviewed_at": datetime.now().isoformat()}
    save_reviewed(reviewed)
    print(f"Approved [{index}] {e.get('title')}")


def cmd_reject(index: int, reason: str | None = None):
    history = load_history()
    reviewed = load_reviewed()
    if index < 0 or index >= len(history):
        print("Index out of range")
        return
    e = history[index]
    key = f"{e.get('source')}|{e.get('learned_at')}|{e.get('title')}"
    reviewed[key] = {"approved": False, "reason": reason, "reviewed_at": datetime.now().isoformat()}
    save_reviewed(reviewed)
    print(f"Rejected [{index}] {e.get('title')} (reason={reason})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true', help='List recent entries')
    parser.add_argument('--interactive', action='store_true', help='Interactive review')
    parser.add_argument('--approve', type=int, help='Approve by index')
    parser.add_argument('--reject', type=int, help='Reject by index')
    parser.add_argument('--reason', type=str, help='Reason for reject/approve')

    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.interactive:
        interactive_review()
    elif args.approve is not None:
        cmd_approve(args.approve, args.reason)
    elif args.reject is not None:
        cmd_reject(args.reject, args.reason)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
