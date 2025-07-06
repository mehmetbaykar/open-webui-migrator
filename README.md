# OpenWebUI Migrator

A tool to migrate your ChatGPT conversations and memories to OpenWebUI.

## Prerequisites

- Docker installed and running
- OpenWebUI running in Docker
- Python 3.8+

## Setup

1. **Prepare the data folder**
   ```bash
   mv .data data
   ```

2. **Configure environment (optional)**
   ```bash
   cp .env.example .env
   ```
   - Add your `USER_ID` if you want to specify it
   - If not set, the script will:
     - Use the single user if only one exists
     - Prompt you to select if multiple users exist

## Export ChatGPT Data

1. Go to ChatGPT → Settings → Data controls → Export data
2. Click "Export" and wait for the email
3. Download the zip file from the email (you have 24 hours)
4. Unzip the file and copy all contents to `data/chatgpt/`

## Export ChatGPT Memories (Optional)

1. Go to ChatGPT → Settings → Personalization → Manage memories
2. Copy all memory entries
3. Paste them into `data/chatgpt/memory.txt`

## Run Migration

```bash
python migrate_all.py
```

The script will:
- Stop your OpenWebUI container
- Backup your database
- Migrate conversations and memories
- Restart OpenWebUI

## Important Notes

- **Images**: ✅ Fully supported
- **Files**: ❌ Not supported (PDFs, JSON, etc.)
  - OpenAI doesn't allow exporting uploaded files, only images
  - Skipped files will be shown in the logs as well as in the chats as a placeholder
- **Duplicates**: Memory entries are automatically deduplicated
- **Chats**: Chats are automatically overridden and no duplicates are allowed

## Troubleshooting

- Ensure Docker is running
- Check that OpenWebUI container name is `open-webui`
- Review logs for any skipped content