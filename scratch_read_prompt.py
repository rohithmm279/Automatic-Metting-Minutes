import json
from pathlib import Path

transcript_path = Path(r"C:\Users\Rohith M\.gemini\antigravity-ide\brain\991c762e-337e-4d82-bb7a-e8875a3a7599\.system_generated\logs\transcript_full.jsonl")

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "USER_INPUT" and "FULL EVALUATION PHASE" in data.get("content", ""):
                with open(r"r:\S5 mini datasets\full_eval_prompt.txt", "w", encoding="utf-8") as out:
                    out.write(data["content"])
                print("Written prompt to full_eval_prompt.txt, length:", len(data["content"]))
                break
        except Exception as e:
            pass
