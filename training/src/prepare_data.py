"""
Export call transcripts from PostgreSQL → JSONL training file for LoRA fine-tuning.
Run before training: python src/prepare_data.py --output /data/train.jsonl
"""
import argparse
import asyncio
import json
import os

import asyncpg

SYSTEM_PROMPT = """You are a helpful AI voice assistant for Indian language calls.
Respond naturally, concisely, and in the same language as the caller."""


async def export_transcripts(output_path: str):
    dsn = (
        f"postgresql://aivoice:{os.environ['POSTGRES_PASSWORD']}"
        f"@postgres:5432/aivoice"
    )
    # async with guarantees connection is closed even if fetch() raises
    async with asyncpg.create_pool(dsn, min_size=1, max_size=3) as pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT room_name,
                       array_agg(event_type ORDER BY created_at) AS types,
                       array_agg(content ORDER BY created_at) AS contents
                FROM call_events
                WHERE event_type IN ('user_speech', 'agent_speech')
                  AND content IS NOT NULL AND content != ''
                GROUP BY room_name
                HAVING count(*) >= 4
                ORDER BY min(created_at)
            """)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for etype, content in zip(row["types"], row["contents"]):
                role = "user" if etype == "user_speech" else "assistant"
                messages.append({"role": role, "content": content})

            user_turns = sum(1 for m in messages if m["role"] == "user")
            if user_turns >= 2:
                f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
                count += 1

    print(f"Exported {count} training examples to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/data/train.jsonl")
    args = parser.parse_args()
    asyncio.run(export_transcripts(args.output))
