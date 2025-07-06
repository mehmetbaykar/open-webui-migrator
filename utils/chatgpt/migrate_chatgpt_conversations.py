#!/usr/bin/env python3
"""Convert ChatGPT exports to open-webui JSON format."""

import json
import os
import re
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
import time
import uuid
from datetime import datetime
from .image_utils import extract_all_files_from_message

INVALID_RE = re.compile(r"[\ue000-\uf8ff]")

# Default fallback model and name
DEFAULT_MODEL = "openai-chatgpt-4o"
DEFAULT_MODEL_NAME = "ChatGPT 4o"


@dataclass
class MessageContext:
    """Context for message processing."""
    default_model: str
    default_model_name: str
    timestamp: float
    stats: Dict[str, int]


def sanitize_text(text: Any) -> str:
    """Return ``text`` without private-use Unicode characters."""
    if not isinstance(text, str):
        return ""
    return INVALID_RE.sub("", text)


def chatgpt_model_to_openwebui(model_slug: str) -> Tuple[str, str]:
    """Convert ChatGPT model slug to open-webui format."""
    model_mapping = {
        "gpt-4": ("openai-gpt-4", "GPT-4"),
        "gpt-4o": ("openai-gpt-4o", "GPT-4o"),
        "gpt-4o-jawboned": ("openai-gpt-4o", "GPT-4o"),
        "gpt-4o-canmore": ("openai-gpt-4o", "GPT-4o"),
        "gpt-4o-mini": ("openai-gpt-4o-mini", "GPT-4o mini"),
        "gpt-4-1": ("openai-gpt-4.1", "GPT-4.1"),
        "gpt-4.1-mini": ("openai-gpt-4.1-mini", "GPT-4.1 mini"),
        "gpt-4.1-nano": ("openai-gpt-4.1-nano", "GPT-4.1 nano"),
        "gpt-4-5": ("openai-gpt-4.5-preview", "GPT-4.5 Preview"),
        "gpt-3.5-turbo": ("openai-gpt-3.5", "GPT-3.5"),
        "o1-preview": ("openai-o1-preview", "o1-preview"),
        "o1-mini": ("openai-o1-mini", "o1-mini"),
        "o3-mini": ("openai-o3-mini", "o3-mini"),
        "o3-mini-high": ("openai-o3-mini-high", "o3-mini-high"),
        "o3": ("openai-o3", "o3"),
        "o4-mini": ("openai-o4-mini", "o4-mini"),
        "o4-mini-high": ("openai-o4-mini-high", "o4-mini-high"),
    }

    if model_slug in model_mapping:
        return model_mapping[model_slug]

    # If not found, try to construct a reasonable default
    if model_slug.startswith("gpt-"):
        return (f"openai-{model_slug}", model_slug.upper())
    if model_slug.startswith("o"):
        return (f"openai-{model_slug}", model_slug)

    # Fallback to default
    return (DEFAULT_MODEL, DEFAULT_MODEL_NAME)


def _process_canvas_content(text_content: str) -> Optional[str]:
    """Process canvas content from JSON text."""
    if not text_content:
        return None
    try:
        data = json.loads(text_content)
        if isinstance(data, dict) and "content" in data:
            content = sanitize_text(data["content"])
            return f"```markdown\n{content}\n```"
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def extract_canvas_from_parts(parts: List[Any]) -> Optional[str]:
    """Extract canvas content from message parts."""
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("content_type") == "code" and part.get("language") == "json":
            result = _process_canvas_content(part.get("text", ""))
            if result:
                return result
    return None


def extract_last_sentence(text: Any) -> str:
    """Return the last sentence of ``text`` if it is a string."""
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def _parts_to_text(parts: List[Any]) -> str:
    """Return concatenated text from ChatGPT message parts."""
    texts: List[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(sanitize_text(part))
        elif isinstance(part, dict):
            # Skip canvas content and image pointers here as they're handled separately
            if part.get("content_type") == "code" and part.get("language") == "json":
                continue
            if part.get("content_type") == "image_asset_pointer":
                continue

            if "text" in part:
                val = part.get("text")
                if isinstance(val, str):
                    texts.append(sanitize_text(val))
    return "".join(texts)


def parse_timestamp(value: Any, default: float) -> float:
    """Convert ``value`` to a Unix timestamp."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return default


def _format_canvas_content(canvas_content: str) -> str:
    """Format canvas content with markdown code blocks if needed."""
    canvas_content = canvas_content.strip()
    if canvas_content.startswith("```markdown") and canvas_content.endswith("```"):
        return canvas_content
    return f"```markdown\n{canvas_content}\n```"


def extract_canvas_content_from_message(msg: dict) -> Optional[str]:
    """Extract canvas content directly from message content."""
    content = msg.get("content", {})

    # Check if this message itself contains canvas content
    if content.get("content_type") == "code" and content.get("language") == "json":
        result = _process_canvas_content(content.get("text", ""))
        if result:
            # Process markdown formatting
            canvas_content = (
                result.replace("```markdown\n", "")
                .rstrip("`").rstrip("\n").rstrip("`")
            )
            return _format_canvas_content(sanitize_text(canvas_content))

    # Also check parts array for canvas content
    parts = content.get("parts", [])
    return extract_canvas_from_parts(parts)


def _init_statistics() -> Dict[str, int]:
    """Initialize statistics dictionary."""
    return {
        "total_conversations": 0,
        "conversations_with_assets": 0,
        "total_assets": 0,
        "total_user_uploads": 0,
        "total_ai_generated": 0,
        "total_non_images": 0,
    }


def _update_asset_statistics(stats: Dict[str, int], file_stats: Dict[str, int]) -> None:
    """Update asset statistics."""
    stats["total_assets"] += len(file_stats.get("files", []))
    stats["total_user_uploads"] += file_stats.get("user_uploaded", 0)
    stats["total_ai_generated"] += file_stats.get("ai_generated", 0)
    stats["total_non_images"] += file_stats.get("non_images", 0)


def _process_simple_message_format(
    item: Dict[str, Any],
    context: MessageContext
) -> Tuple[List[Dict[str, Any]], bool]:
    """Process messages in simple format."""
    messages = []
    conversation_has_assets = False

    if not isinstance(item.get("chat_messages"), list):
        return messages, conversation_has_assets

    for idx, msg in enumerate(item["chat_messages"]):
        # Extract text and files
        text = _extract_message_text(msg)
        files, file_stats = extract_all_files_from_message(msg)

        if files:
            conversation_has_assets = True
            _update_asset_statistics(context.stats, {"files": files, **file_stats})

        if text:
            # Determine role and model
            role = "user" if idx % 2 == 0 else "assistant"
            model, model_name = _get_simple_message_model(msg, role, context)

            messages.append({
                "role": role,
                "content": text,
                "timestamp": context.timestamp,
                "model": model,
                "model_name": model_name,
                "files": files,
            })

    return messages, conversation_has_assets


def _extract_message_text(msg: Dict[str, Any]) -> str:
    """Extract text from a message."""
    text = msg.get("text")
    if not text and isinstance(msg.get("content"), list):
        text = _parts_to_text(msg["content"])
    return sanitize_text(text)


def _get_simple_message_model(
    msg: Dict[str, Any], role: str, context: MessageContext
) -> Tuple[str, str]:
    """Get model for simple message format."""
    if role == "user":
        return context.default_model, context.default_model_name

    model_slug = msg.get("metadata", {}).get("model_slug")
    if model_slug:
        return chatgpt_model_to_openwebui(model_slug)
    return context.default_model, context.default_model_name


def _process_message_node(
    msg: Dict[str, Any],
    context: MessageContext
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process a single message node and return regular message, canvas message, and files."""
    # Extract all files from message
    files, file_stats = extract_all_files_from_message(msg)
    if files:
        _update_asset_statistics(context.stats, {"files": files, **file_stats})

    # Build messages based on content type
    role = msg.get("author", {}).get("role", "assistant")
    ts_val = parse_timestamp(
        msg.get("create_time") or msg.get("timestamp") or context.timestamp,
        context.timestamp
    )
    model, model_name = _get_message_model(
        msg, role, context.default_model, context.default_model_name
    )

    # Build message info dict
    message_info = {
        "timestamp": ts_val,
        "model": model,
        "model_name": model_name,
        "files": files
    }

    # Try to extract canvas content first
    canvas_content = extract_canvas_content_from_message(msg)
    canvas_msg = (
        _build_message(role, canvas_content, message_info)
        if canvas_content else None
    )

    # Process regular text parts
    text = sanitize_text(_parts_to_text(msg.get("content", {}).get("parts", [])))
    regular_msg = None

    if text and text.strip() and role in {"user", "assistant"} and not canvas_content:
        regular_msg = _build_message(role, text, message_info)

    return regular_msg, canvas_msg, files


def _get_message_model(
    msg: Dict[str, Any],
    role: str,
    default_model: str,
    default_model_name: str
) -> Tuple[str, str]:
    """Get model information for a message."""
    if role == "user":
        return default_model, default_model_name

    model_slug = msg.get("metadata", {}).get("model_slug")
    if model_slug:
        return chatgpt_model_to_openwebui(model_slug)
    return (default_model, default_model_name)


def _build_message(
    role: str,
    content: str,
    message_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Build a message dictionary."""
    return {
        "role": role,
        "content": content,
        "timestamp": message_info["timestamp"],
        "model": message_info["model"],
        "model_name": message_info["model_name"],
        "files": message_info["files"],
    }


def _process_mapping_format(
    mapping: Dict[str, Any],
    current_id: Optional[str],
    context: MessageContext
) -> Tuple[List[Dict[str, Any]], bool]:
    """Process conversation in mapping format."""
    messages = []
    has_assets = False

    if not current_id or not isinstance(mapping.get(current_id), dict):
        return messages, has_assets

    # Start from current node and traverse backwards
    node = mapping[current_id]
    stack: List[Dict[str, Any]] = []

    while isinstance(node, dict):
        msg = node.get("message") or {}
        regular_msg, canvas_msg, files = _process_message_node(msg, context)

        if files:
            has_assets = True

        if canvas_msg:
            stack.append(canvas_msg)
        if regular_msg:
            stack.append(regular_msg)

        parent_id = node.get("parent")
        if not parent_id:
            break
        node = mapping.get(parent_id)

    messages.extend(reversed(stack))
    return messages, has_assets


def _process_alternative_mapping(
    mapping: Dict[str, Any],
    context: MessageContext
) -> Tuple[List[Dict[str, Any]], bool]:
    """Process conversation using alternative traversal method."""
    messages = []
    has_assets = False

    # Find root node
    node = mapping.get("client-created-root")
    if not isinstance(node, dict):
        # Find root node by looking for entry with no parent
        for val in mapping.values():
            if isinstance(val, dict) and not val.get("parent"):
                node = val
                break

    if not isinstance(node, dict):
        return messages, has_assets

    next_ids = node.get("children") or []
    while next_ids:
        node = mapping.get(next_ids[0])
        if not isinstance(node, dict):
            break

        msg = node.get("message") or {}
        regular_msg, canvas_msg, files = _process_message_node(msg, context)

        if files:
            has_assets = True

        if canvas_msg:
            messages.append(canvas_msg)
        if regular_msg:
            messages.append(regular_msg)

        next_ids = node.get("children") or []

    return messages, has_assets


def parse_chatgpt(data: Any) -> List[dict]:
    """Parse ChatGPT conversation data and extract structured information."""
    conversations = data if isinstance(data, list) else [data]
    result = []
    stats = _init_statistics()
    stats["total_conversations"] = len(conversations)

    for item in conversations:
        if not isinstance(item, dict):
            continue

        processed_conv = _process_conversation_item(item, stats)
        if processed_conv:
            result.append(processed_conv)

    _log_statistics(stats)
    return result


def _process_conversation_item(
    item: Dict[str, Any], stats: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """Process a single conversation item."""
    # Extract basic conversation info
    conv_info = _extract_conversation_info(item)

    # Create context for message processing
    context = MessageContext(
        default_model=conv_info["default_model"],
        default_model_name=conv_info["default_model_name"],
        timestamp=conv_info["timestamp"],
        stats=stats
    )

    # Process messages based on format
    messages, has_assets = _extract_messages_from_item(item, context)

    if has_assets:
        stats["conversations_with_assets"] += 1

    return {
        "title": conv_info["title"],
        "timestamp": conv_info["timestamp"],
        "messages": messages,
        "conversation_id": conv_info["id"],
        "default_model": conv_info["default_model"],
        "default_model_name": conv_info["default_model_name"],
    }


def _extract_conversation_info(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract basic information from conversation item."""
    title = item.get("title") or item.get("name") or "Untitled"
    ts_raw = item.get("create_time") or item.get("update_time") or time.time()
    ts = parse_timestamp(ts_raw, time.time())
    conv_id = item.get("conversation_id") or item.get("id")

    # Extract default model
    default_model_slug = item.get("default_model_slug")
    default_model, default_model_name = (
        chatgpt_model_to_openwebui(default_model_slug)
        if default_model_slug
        else (DEFAULT_MODEL, DEFAULT_MODEL_NAME)
    )

    return {
        "title": title,
        "timestamp": ts,
        "id": conv_id,
        "default_model": default_model,
        "default_model_name": default_model_name,
    }


def _extract_messages_from_item(
    item: Dict[str, Any],
    context: MessageContext
) -> Tuple[List[Dict[str, Any]], bool]:
    """Extract messages from conversation item based on format."""
    messages: List[Dict[str, Any]] = []
    has_assets = False

    if isinstance(item.get("chat_messages"), list):
        # Simple message format
        messages, has_assets = _process_simple_message_format(item, context)
    elif isinstance(item.get("mapping"), dict):
        # Complex mapping format
        messages, has_assets = _process_complex_mapping(item, context)
    else:
        # Fallback case
        messages.append(_create_fallback_message(
            item.get("title") or "Untitled",
            context.timestamp,
            context.default_model,
            context.default_model_name
        ))

    return messages, has_assets


def _process_complex_mapping(
    item: Dict[str, Any],
    context: MessageContext
) -> Tuple[List[Dict[str, Any]], bool]:
    """Process complex mapping format conversations."""
    mapping = item["mapping"]
    messages, has_assets = _process_mapping_format(
        mapping, item.get("current_node"), context
    )

    # Try alternative traversal if no messages found
    if not messages:
        alt_messages, alt_has_assets = _process_alternative_mapping(mapping, context)
        messages.extend(alt_messages)
        has_assets = has_assets or alt_has_assets

    return messages, has_assets


def _create_fallback_message(
    title: str, ts: float, model: str, model_name: str
) -> Dict[str, Any]:
    """Create a fallback message when no proper format is found."""
    return {
        "role": "user",
        "content": title,
        "timestamp": ts,
        "model": model,
        "model_name": model_name,
        "files": [],
    }


def _log_statistics(stats: Dict[str, int]) -> None:
    """Log parsing statistics."""
    print(f"Parsed {stats['total_conversations']} conversations")
    print(f"Found {stats['conversations_with_assets']} conversations with assets")
    print(
        f"Total assets: {stats['total_assets']} "
        f"(Images: {stats['total_user_uploads'] + stats['total_ai_generated']}, "
        f"Non-images: {stats['total_non_images']})"
    )
    print(f"  - User-uploaded images: {stats['total_user_uploads']}")
    print(f"  - AI-generated images: {stats['total_ai_generated']}")
    print(f"  - Non-image files (PDFs, JSON, etc.): {stats['total_non_images']}")
    if stats['total_non_images'] > 0:
        print("  Note: Non-image file content not available in ChatGPT export")


def clean_file_data(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean file data for storage in OpenWebUI format."""
    cleaned_files = []
    for f in files:
        cleaned_file = {}
        for key, value in f.items():
            # Skip internal tracking fields
            if not key.startswith("_"):
                cleaned_file[key] = value
        cleaned_files.append(cleaned_file)
    return cleaned_files


def build_webui(conversation: dict, user_id: str = "user") -> Tuple[Dict[str, Any], str]:
    """Build OpenWebUI format conversation from parsed ChatGPT data."""
    conv_uuid = str(uuid.uuid4())

    # Process messages and collect metadata
    messages_data = _process_conversation_messages(conversation["messages"])

    # Build conversation structure
    conv_id = conversation.get("conversation_id") or conv_uuid
    if not conv_id:
        raise ValueError(
            f"No conversation ID found for conversation: {conversation.get('title', 'Unknown')}"
        )

    webui = _build_webui_structure(
        conv_id=conv_id,
        conversation=conversation,
        messages_data=messages_data,
        user_id=user_id
    )

    return webui, conv_uuid


def _process_conversation_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process messages and collect metadata."""
    messages_map: Dict[str, Any] = {}
    messages_list: List[Dict[str, Any]] = []
    models_used = set()
    conversation_files_with_metadata = []
    prev_id: Optional[str] = None

    for msg_data in messages:
        msg_id = str(uuid.uuid4())

        # Build message object
        msg = _build_webui_message(msg_data, msg_id, prev_id)
        models_used.add(msg_data["model"])

        # Process files
        message_files = msg_data.get("files", [])
        if message_files:
            conversation_files_with_metadata.extend(message_files)
            msg["files"] = clean_file_data(message_files)

        # Update message graph
        if prev_id:
            messages_map[prev_id]["childrenIds"].append(msg_id)
        messages_map[msg_id] = msg
        messages_list.append(msg)
        prev_id = msg_id

    return {
        "messages_map": messages_map,
        "messages_list": messages_list,
        "models_used": models_used,
        "files_with_metadata": conversation_files_with_metadata,
        "last_id": prev_id
    }


def _build_webui_message(
    msg_data: Dict[str, Any], msg_id: str, parent_id: Optional[str]
) -> Dict[str, Any]:
    """Build a single WebUI message structure."""
    clean_content = sanitize_text(msg_data["content"])

    msg = {
        "id": msg_id,
        "parentId": parent_id,
        "childrenIds": [],
        "role": msg_data["role"],
        "content": clean_content,
        "timestamp": int(msg_data["timestamp"]),
    }

    if msg_data["role"] == "user":
        msg["models"] = [msg_data["model"]]
    else:
        msg.update({
            "model": msg_data["model"],
            "modelName": msg_data["model_name"],
            "modelIdx": 0,
            "userContext": None,
            "lastSentence": extract_last_sentence(clean_content),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "done": True,
        })

    return msg


def _build_webui_structure(
    conv_id: str,
    conversation: Dict[str, Any],
    messages_data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """Build the final WebUI conversation structure."""
    primary_model = conversation.get("default_model", DEFAULT_MODEL)
    models_used = messages_data["models_used"]

    webui = {
        "id": conv_id,
        "title": conversation["title"],
        "models": list(models_used) if models_used else [primary_model],
        "params": {},
        "history": {
            "messages": messages_data["messages_map"],
            "currentId": messages_data["last_id"]
        },
        "messages": messages_data["messages_list"],
        "tags": [],
        "timestamp": int(conversation["timestamp"] * 1000),
        "files": clean_file_data(messages_data["files_with_metadata"]),
        "_files_with_metadata": messages_data["files_with_metadata"],
    }

    if user_id:
        webui["userId"] = user_id

    return webui


def slugify(text: Any) -> str:
    """Create a URL-safe slug from text."""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^a-zA-Z0-9_\-]", "", text)
    return text[:50] or "chat"


def convert_file(path: str, user_id: str = "user", outdir: str = "output/chatgpt") -> None:
    """Convert ChatGPT export file to OpenWebUI format JSON files."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conversations = parse_chatgpt(data)
    os.makedirs(outdir, exist_ok=True)

    for conv in conversations:
        out, conv_uuid = build_webui(conv, user_id)
        conv_id = conv.get("conversation_id")
        unique = conv_id if conv_id else conv_uuid
        fname = f"{slugify(conv['title'])}_{unique}.json"

        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def convert_conversations_to_openwebui_format(
    chatgpt_data: Any, user_id: str = "user"
) -> List[Dict[str, Any]]:
    """Convert ChatGPT data to OpenWebUI format and return as list of conversations."""
    conversations = parse_chatgpt(chatgpt_data)
    result = []

    for conv in conversations:
        webui_conv, _ = build_webui(conv, user_id)
        result.append(webui_conv)

    return result
