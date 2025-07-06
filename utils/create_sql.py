"""Generate SQL insert statements from open-webui chat JSON files."""

import argparse
import json
import os
import re
import uuid


def load_json(path: str) -> dict:
    """Load and parse JSON file from given path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: str) -> str:
    """Load plain text file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def escape_sql_string(value: str) -> str:
    """Escape single quotes in SQL strings."""
    if not isinstance(value, str):
        value = str(value)
    return value.replace("'", "''")


def build_meta(tags: list[str]) -> str:
    """Build metadata JSON string with tags."""
    meta = json.dumps({"tags": tags}, ensure_ascii=True)
    return escape_sql_string(meta)


def slugify(value: str) -> str:
    """Return a slug suitable for use as an identifier."""
    value = value.lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def tag_upserts(user_id: str, meta_tags: list[str]) -> list[str]:
    """Return SQL statements to ensure tags exist for the user."""
    base_tags = [
        ("imported-grok", "imported-grok"),
        ("imported-chatgpt", "imported-chatgpt"),
        ("imported-claude", "imported-claude"),
    ]
    for t in meta_tags:
        slug = slugify(t)
        base_tags.append((slug, t))

    unique: dict[str, str] = {}
    for tag_id, name in base_tags:
        unique[tag_id] = name

    stmts = []
    for tag_id, name in unique.items():
        stmts.append(
            'INSERT INTO "main"."tag" ("id","name","user_id","meta") '
            f"VALUES ('{tag_id}','{name}','{user_id}','null') "
            'ON CONFLICT("id","user_id") DO UPDATE SET "name"=excluded."name";'
        )
    return stmts


def conversation_to_sql(
    conversation: dict, tags: list[str], default_user_id: str = "user"
) -> tuple[str, str]:
    """Convert a single OpenWebUI conversation to SQL format."""
    # Extract user_id, falling back to default if not present
    user_id = conversation.get("userId", default_user_id)

    # Convert conversation to JSON
    chat_json = json.dumps(conversation, ensure_ascii=True)
    chat_json = escape_sql_string(chat_json)

    # Extract metadata
    title = escape_sql_string(conversation.get("title", "Untitled"))
    record_id = conversation.get("id", str(uuid.uuid4()))
    timestamp = conversation.get("timestamp", 0)

    # Convert to seconds if it appears to be in milliseconds
    if timestamp > 10000000000:
        timestamp = timestamp // 1000

    # Build metadata with tags
    meta = build_meta(tags)

    # Generate SQL
    sql = (
        f'DELETE FROM "main"."chat" WHERE "id" = \'{record_id}\';\n'
        'INSERT INTO "main"."chat" '
        '("id","user_id","title","share_id","archived","created_at",'
        '"updated_at","chat","pinned","meta","folder_id")\n'
        f"VALUES ('{record_id}','{user_id}','{title}',NULL,0,"
        f"{timestamp},{timestamp},'{chat_json}',0,'{meta}',NULL);"
    )

    return sql, user_id


def memory_to_sql(
    memory_text: str, tags: list[str], default_user_id: str = "user"
) -> tuple[str, str]:
    """Convert memory text to SQL format as a special chat."""
    # Create a fake conversation structure for memory
    memory_conversation = {
        "title": "Custom Instructions / Memory",
        "messages": [{"role": "system", "content": memory_text, "timestamp": 0}],
        "create_time": 0,
        "id": "memory-" + str(uuid.uuid4()),
    }

    chat_json = json.dumps(memory_conversation, ensure_ascii=True)
    chat_json = escape_sql_string(chat_json)

    title = escape_sql_string("Custom Instructions / Memory")
    record_id = "memory-" + str(uuid.uuid4())
    user_id = default_user_id
    created_at = 0

    meta = build_meta(tags + ["memory", "custom-instructions"])

    sql = (
        f'DELETE FROM "main"."chat" WHERE "id" = \'{record_id}\';\n'
        'INSERT INTO "main"."chat" '
        '("id","user_id","title","share_id","archived","created_at",'
        '"updated_at","chat","pinned","meta","folder_id")\n'
        f"VALUES ('{record_id}','{user_id}','{title}',NULL,0,"
        f"{created_at},{created_at},'{chat_json}',0,'{meta}',NULL);"
    )
    return sql, user_id


def json_to_sql(path: str, tags: list[str]) -> tuple[str, str]:
    """Convert JSON file to SQL statements."""
    data = load_json(path)

    # Check if this is an array of conversations or a single conversation
    if isinstance(data, list):
        # Array of conversations (could be ChatGPT export or multiple OpenWebUI conversations)
        if not data:
            raise ValueError(f"No conversations found in {path}")

        all_sql = []
        user_ids = set()

        for conversation in data:
            if isinstance(conversation, dict):
                sql, user_id = conversation_to_sql(conversation, tags)
                all_sql.append(sql)
                user_ids.add(user_id)

        combined_sql = "\n".join(all_sql)
        # Return first user_id for tag creation
        return combined_sql, list(user_ids)[0] if user_ids else "user"

    # Single conversation object (OpenWebUI format)
    if isinstance(data, dict):
        return conversation_to_sql(data, tags)

    raise ValueError(f"Invalid JSON format in {path}")


def file_to_sql(path: str, tags: list[str]) -> tuple[str, str]:
    """Convert file to SQL statements, detecting format automatically."""
    # Check file extension and content to determine format
    _, ext = os.path.splitext(path.lower())

    if ext == ".txt":
        # Handle as plain text (memory/custom instructions)
        memory_text = load_text(path)
        if not memory_text:
            raise ValueError(f"Empty memory file: {path}")
        return memory_to_sql(memory_text, tags)

    if ext == ".json":
        # Handle as JSON (conversations)
        return json_to_sql(path, tags)

    # Try to detect by content
    try:
        # Try parsing as JSON first
        return json_to_sql(path, tags)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Fall back to text
        memory_text = load_text(path)
        if not memory_text:
            raise ValueError(f"Empty file: {path}") from exc
        return memory_to_sql(memory_text, tags)


def gather_files(paths: list[str]) -> list[str]:
    """Gather all JSON and text files from given paths."""
    result = []
    for p in paths:
        if os.path.isdir(p):
            for name in os.listdir(p):
                if name.endswith(".json") or name.endswith(".txt"):
                    result.append(os.path.join(p, name))
        else:
            result.append(p)
    return result


def main() -> None:
    """Main entry point for SQL generation script."""
    parser = argparse.ArgumentParser(description="Create SQL inserts for open-webui chats")
    parser.add_argument("files", nargs="+", help="Chat JSON files or directories")
    parser.add_argument(
        "--tags", default="imported", help="Comma-separated tags for the meta field"
    )
    parser.add_argument("--output", help="Write SQL statements to this file")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] or ["imported"]

    files = gather_files(args.files)
    inserts = []
    user_ids: set[str] = set()
    for fpath in files:
        try:
            sql, uid = file_to_sql(fpath, tags)
            inserts.append(sql)
            user_ids.add(uid)
        except Exception as exc:
            raise SystemExit(f"Failed to process {fpath}: {exc}") from exc

    prefix = []
    for uid in sorted(user_ids):
        prefix.extend(tag_upserts(uid, tags))

    output = "\n".join(prefix + inserts)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
