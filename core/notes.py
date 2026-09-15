import json
import os
from datetime import datetime
from typing import Optional


NOTES_FILE = "data/stock_notes.json"


def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r") as f:
            return json.load(f)
    return {"notes": {}}


def save_notes(data):
    os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
    with open(NOTES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_notes(symbol: str) -> list:
    data = load_notes()
    return data.get("notes", {}).get(symbol, [])


def add_note(symbol: str, note: str, category: str = "general") -> dict:
    data = load_notes()
    if symbol not in data.get("notes", {}):
        data.setdefault("notes", {})[symbol] = []
    
    note_entry = {
        "id": len(data["notes"][symbol]) + 1,
        "note": note,
        "category": category,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    data["notes"][symbol].append(note_entry)
    save_notes(data)
    return note_entry


def delete_note(symbol: str, note_id: int) -> bool:
    data = load_notes()
    if symbol in data.get("notes", {}):
        data["notes"][symbol] = [n for n in data["notes"][symbol] if n["id"] != note_id]
        save_notes(data)
        return True
    return False


def get_all_notes() -> dict:
    data = load_notes()
    result = []
    for symbol, notes in data.get("notes", {}).items():
        for note in notes:
            result.append({
                "symbol": symbol,
                **note
            })
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"notes": result, "count": len(result)}
