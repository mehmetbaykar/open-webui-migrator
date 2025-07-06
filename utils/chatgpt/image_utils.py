"""Utilities for handling image assets during ChatGPT to OpenWebUI migration."""

import base64
import os
import re
from typing import Optional, Dict, List, Tuple, Any
import mimetypes


def get_image_mime_type(filename: str) -> str:
    """Get MIME type for an image file based on extension."""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.startswith("image/"):
        return mime_type

    # Fallback for common image types
    ext_to_mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    ext = os.path.splitext(filename.lower())[1]
    return ext_to_mime.get(ext, "image/jpeg")  # Default to JPEG


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """Encode an image file to base64 data URL format."""
    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_encoded = base64.b64encode(image_data).decode("utf-8")
            mime_type = get_image_mime_type(image_path)
            return f"data:{mime_type};base64,{base64_encoded}"
    except (OSError, IOError) as e:
        print(f"Error: Failed to encode image {image_path}: {e}")
        return None


def extract_file_id_from_asset_pointer(asset_pointer: str) -> Optional[str]:
    """Extract file ID from ChatGPT asset pointer URL."""
    # Format: "file-service://file-XXXXXX"
    match = re.match(r"file-service://file-(.+)", asset_pointer)
    if match:
        return f"file-{match.group(1)}"
    return None


def find_image_file(file_id: str, data_dir: str) -> Optional[str]:
    """Find the actual image file in the data directory based on file ID."""
    # Check main data directory first
    try:
        for filename in os.listdir(data_dir):
            if filename.startswith(file_id):
                full_path = os.path.join(data_dir, filename)
                if os.path.isfile(full_path):
                    return full_path
    except (OSError, IOError) as e:
        print(f"Error searching for file {file_id} in {data_dir}: {e}")

    # Check dalle-generations subdirectory
    dalle_dir = os.path.join(data_dir, "dalle-generations")
    if os.path.exists(dalle_dir):
        try:
            for filename in os.listdir(dalle_dir):
                if filename.startswith(file_id):
                    full_path = os.path.join(dalle_dir, filename)
                    if os.path.isfile(full_path):
                        return full_path
        except (OSError, IOError) as e:
            print(f"Error searching for file {file_id} in {dalle_dir}: {e}")

    return None


def is_ai_generated_image(
    attachment: Dict[str, Any],
    message_metadata: Dict[str, Any],
    file_path: Optional[str] = None,
) -> bool:
    """Determine if an image is AI-generated based on metadata and file location."""
    # Check for DALL-E generation in metadata
    if message_metadata.get("dalle"):
        return True

    # Check for specific patterns in attachment data
    attachment_id = attachment.get("id", "")
    if "dalle" in attachment_id.lower():
        return True

    # Check if file path contains dalle-generations
    if file_path and "dalle-generations" in file_path:
        return True

    # Check if file exists in dalle-generations folder
    dalle_dir = "data/chatgpt/dalle-generations"
    if os.path.exists(dalle_dir):
        for filename in os.listdir(dalle_dir):
            if filename.startswith(attachment_id):
                return True

    # Default to user-uploaded
    return False


def _process_image_attachment(
    attachment: Dict[str, Any],
    file_id: str,
    message_metadata: Dict[str, Any],
    data_dir: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Process a single image attachment."""
    # Find the actual file
    image_path = find_image_file(file_id, data_dir)
    if not image_path:
        print(f"Warning: Image file not found for ID: {file_id}")
        return None, "missing"

    # Determine if AI-generated
    if is_ai_generated_image(attachment, message_metadata, image_path):
        # For AI-generated images, we'll store the path reference
        file_data = {
            "type": "image",
            "url": f"uploads/{os.path.basename(image_path)}",
            "name": attachment.get("name", os.path.basename(image_path)),
            "size": attachment.get("size", 0),
            "ai_generated": True,
            "source_path": image_path,
        }
    else:
        # For user-uploaded images, encode to base64
        base64_url = encode_image_to_base64(image_path)
        if not base64_url:
            return None, "failed"
        file_data = {
            "type": "image",
            "url": base64_url,
            "name": attachment.get("name", os.path.basename(image_path)),
            "size": attachment.get("size", 0),
        }

    return file_data, "found"


def _process_non_image_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
    """Process a non-image attachment."""
    mime_type = attachment.get("mime_type", "application/octet-stream")
    file_name = attachment.get("name", "unknown")

    # Determine file type from mime type
    file_type = "file"  # Default
    if mime_type.startswith("application/pdf"):
        file_type = "pdf"
    elif mime_type.startswith("text/"):
        file_type = "text"
    elif mime_type in ["application/json", "application/xml"]:
        file_type = "code"

    return {
        "type": file_type,
        "name": file_name,
        "size": attachment.get("size", 0),
        "mime_type": mime_type,
        "_migration_note": "File content not available - ChatGPT only exports image assets",
        "_original_id": attachment.get("id"),
    }


def process_all_attachments(
    attachments: List[Dict[str, Any]],
    parts: List[Any],
    message_metadata: Dict[str, Any],
    data_dir: str = "data/chatgpt",
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Process all attachments (images and non-images) and return OpenWebUI file format."""
    files = []
    stats = {"images_found": 0, "images_missing": 0, "non_images": 0}

    # Create a mapping of attachment IDs to attachment data
    attachment_map = {att.get("id"): att for att in attachments if att.get("id")}

    # Track which attachments have been processed via parts
    processed_ids = set()

    # Process parts to find image asset pointers
    for part in parts:
        if isinstance(part, dict) and part.get("content_type") == "image_asset_pointer":
            asset_pointer = part.get("asset_pointer", "")
            file_id = extract_file_id_from_asset_pointer(asset_pointer)

            if not file_id:
                continue

            processed_ids.add(file_id)

            # Find the corresponding attachment
            attachment = attachment_map.get(file_id)
            if not attachment:
                print(f"Warning: No attachment found for file ID: {file_id}")
                continue

            # Process the image attachment
            file_data, status = _process_image_attachment(
                attachment, file_id, message_metadata, data_dir
            )

            if status == "missing":
                stats["images_missing"] += 1
            elif status == "found":
                stats["images_found"] += 1
                if file_data:
                    files.append(file_data)

    # Process remaining attachments that weren't found in parts (non-images)
    for att_id, attachment in attachment_map.items():
        if att_id not in processed_ids:
            # This is a non-image attachment
            file_data = _process_non_image_attachment(attachment)
            files.append(file_data)
            stats["non_images"] += 1

            print(
                f"Info: Non-image file detected: {file_data['name']} "
                f"({file_data['mime_type']}) - content not available in export"
            )

    return files, stats


def process_image_attachments(
    attachments: List[Dict[str, Any]],
    parts: List[Any],
    message_metadata: Dict[str, Any],
    data_dir: str = "data/chatgpt",
) -> List[Dict[str, Any]]:
    """Process image attachments and return OpenWebUI file format.

    This is a compatibility wrapper for the new process_all_attachments function.
    """
    files, _ = process_all_attachments(attachments, parts, message_metadata, data_dir)
    # Filter to only return image files for backward compatibility
    return [
        f for f in files if f.get("type") == "image" or f.get("url", "").startswith("data:image")
    ]


def extract_images_from_message(
    message: Dict[str, Any], data_dir: str = "data/chatgpt"
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Extract all images from a message and return files list and statistics."""
    files = []
    stats = {"user_uploaded": 0, "ai_generated": 0, "failed": 0}

    # Get attachments and metadata
    attachments = message.get("metadata", {}).get("attachments", [])
    message_metadata = message.get("metadata", {})

    # Get message parts
    content = message.get("content", {})
    parts = content.get("parts", [])

    if attachments:
        processed_files = process_image_attachments(attachments, parts, message_metadata, data_dir)

        for file_data in processed_files:
            files.append(file_data)
            if file_data.get("ai_generated"):
                stats["ai_generated"] += 1
            else:
                stats["user_uploaded"] += 1

    return files, stats


def extract_all_files_from_message(
    message: Dict[str, Any], data_dir: str = "data/chatgpt"
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Extract all files from a message and return files list and statistics."""
    files = []
    stats = {"user_uploaded": 0, "ai_generated": 0, "non_images": 0, "failed": 0}

    # Get attachments and metadata
    attachments = message.get("metadata", {}).get("attachments", [])
    message_metadata = message.get("metadata", {})

    # Get message parts
    content = message.get("content", {})
    parts = content.get("parts", [])

    if attachments:
        processed_files, processing_stats = process_all_attachments(
            attachments, parts, message_metadata, data_dir
        )

        for file_data in processed_files:
            files.append(file_data)
            # Count based on file type
            if "_migration_note" in file_data:  # Non-image file
                stats["non_images"] += 1
            elif file_data.get("ai_generated"):
                stats["ai_generated"] += 1
            else:
                stats["user_uploaded"] += 1

        # Add failed images to stats
        stats["failed"] = processing_stats.get("images_missing", 0)

    return files, stats


def get_ai_generated_images_to_copy(
    conversations: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """Get list of AI-generated images that need to be copied to Docker volume."""
    images_to_copy = []

    for conv in conversations:
        # Check the special metadata field first
        if "_files_with_metadata" in conv:
            for file_data in conv["_files_with_metadata"]:
                if file_data.get("ai_generated") and "source_path" in file_data:
                    source = file_data["source_path"]
                    # Destination will be in the Docker volume's uploads directory
                    dest_name = os.path.basename(source)
                    images_to_copy.append((source, dest_name))

        # Also check messages for files with metadata
        if "messages" in conv:
            for msg in conv["messages"]:
                if "files" in msg:
                    # This won't have metadata anymore, skip
                    continue

    # Remove duplicates while preserving order
    seen = set()
    unique_images = []
    for item in images_to_copy:
        if item not in seen:
            seen.add(item)
            unique_images.append(item)

    return unique_images
