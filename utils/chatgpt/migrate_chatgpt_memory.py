"""Migrate memory entries for open-webui from memory.txt file."""

import re
import time
import uuid
from typing import List


def sanitize_text(text: str) -> str:
    """Clean and sanitize memory text."""
    if not isinstance(text, str):
        return ""
    # Remove extra whitespace and normalize
    text = re.sub(r"\s+", " ", text.strip())
    return text


def parse_memory_file(file_path: str) -> List[str]:
    """Parse memory.txt and extract individual memories separated by blank lines."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by double newlines (blank lines) to separate memories
    memories = []
    raw_memories = content.split("\n\n")

    for memory in raw_memories:
        clean_memory = sanitize_text(memory)
        if clean_memory and len(clean_memory.strip()) > 10:  # Filter out very short entries
            memories.append(clean_memory)

    return memories


def parse_memory_text(content: str) -> List[str]:
    """Parse memory text content and extract individual memories."""
    # Split by double newlines (blank lines) to separate memories
    memories = []
    raw_memories = content.split("\n\n")

    for memory in raw_memories:
        clean_memory = sanitize_text(memory)
        if clean_memory and len(clean_memory.strip()) > 10:  # Filter out very short entries
            memories.append(clean_memory)

    return memories


def create_memory_sql(
    memories: List[str], user_id: str = "user", remove_existing: bool = True
) -> str:
    """Create SQL statements for memory inserts and return as string.
    
    Args:
        memories: List of memory content strings
        user_id: User ID to associate memories with
        remove_existing: If True, removes all existing memories before inserting.
                        If False, skips duplicate memories based on content.
    """
    current_time = int(time.time())

    sql_statements = []
    sql_statements.append("-- Memory entries for open-webui")
    sql_statements.append("-- Generated at: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    sql_statements.append("")

    if remove_existing:
        # Clear existing memories for this user
        sql_statements.append(f"-- Clear existing memories for user {user_id}")
        sql_statements.append(f"DELETE FROM memory WHERE user_id = '{user_id}';")
        sql_statements.append("")

        # When removing existing, we can use simple INSERT statements
        for i, memory_content in enumerate(memories, 1):
            memory_id = str(uuid.uuid4())

            # Escape single quotes for SQL
            escaped_content = memory_content.replace("'", "''")
            sql_statement = f"""-- Memory {i}
INSERT INTO memory (id, user_id, content, created_at, updated_at)
VALUES ('{memory_id}', '{user_id}', '{escaped_content}', {current_time}, {current_time});"""

            sql_statements.append(sql_statement)
            sql_statements.append("")
    else:
        # When not removing existing, check for duplicates
        sql_statements.append("-- Skipping duplicate memories based on content")
        sql_statements.append("")

        for i, memory_content in enumerate(memories, 1):
            memory_id = str(uuid.uuid4())

            # Escape single quotes for SQL
            escaped_content = memory_content.replace("'", "''")

            # Use INSERT ... WHERE NOT EXISTS to avoid duplicates
            sql_statement = f"""-- Memory {i}
INSERT INTO memory (id, user_id, content, created_at, updated_at)
SELECT '{memory_id}', '{user_id}', '{escaped_content}', {current_time}, {current_time}
WHERE NOT EXISTS (
    SELECT 1 FROM memory
    WHERE user_id = '{user_id}'
    AND content = '{escaped_content}'
);"""

            sql_statements.append(sql_statement)
            sql_statements.append("")

    return "\n".join(sql_statements)


def create_memory_sql_file(
    memories: List[str],
    user_id: str = "user",
    output_file: str = "memory.sql",
    remove_existing: bool = True,
) -> None:
    """Create SQL file with memory inserts."""
    sql_content = create_memory_sql(memories, user_id, remove_existing)

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(sql_content)

    print(f"Created SQL file: {output_file}")
    print(f"Generated {len(memories)} memory entries for user {user_id}")


def convert_memory_file_to_sql(
    memory_file_path: str,
    user_id: str = "user",
    output_file: str = "memory.sql",
    remove_existing: bool = True,
) -> str:
    """Convert memory file to SQL statements and optionally save to file."""
    memories = parse_memory_file(memory_file_path)

    if not memories:
        raise ValueError("No memories found in the input file.")

    sql_content = create_memory_sql(memories, user_id, remove_existing)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(sql_content)
        print(f"Created SQL file: {output_file}")
        print(f"Generated {len(memories)} memory entries for user {user_id}")

    return sql_content


def convert_memory_text_to_sql(
    memory_text: str, user_id: str = "user", remove_existing: bool = True
) -> str:
    """Convert memory text content to SQL statements."""
    memories = parse_memory_text(memory_text)

    if not memories:
        raise ValueError("No memories found in the input text.")

    return create_memory_sql(memories, user_id, remove_existing)
