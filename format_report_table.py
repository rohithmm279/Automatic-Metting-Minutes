import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import json
from pathlib import Path

ROOT = Path(r"r:\S5 mini datasets")
with open(ROOT / "qwen_eval_prompt_v2_affected_raw.json", "r", encoding="utf-8") as f:
    data = json.load(f)

per_m = data["per_meeting"]
agg = data["aggregate"]

print("Per-Meeting Comparison Table:")
print("| Meeting | V1 Issue F1 | V2 Issue F1 | Δ Issue | V1 Dec F1 | V2 Dec F1 | Δ Dec | V1 AI F1 | V2 AI F1 | Δ AI |")
print("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

for m in per_m:
    m_id = m["meeting_id"]
    iss1 = m["v1_sem_iss_f1"]
    iss2 = m["sem_iss_f1"]
    diss = m["delta_sem_iss_f1"]
    
    dec1 = m["v1_sem_dec_f1"]
    dec2 = m["sem_dec_f1"]
    ddec = m["delta_sem_dec_f1"]
    
    ai1 = m["v1_sem_ai_f1"]
    ai2 = m["sem_ai_f1"]
    dai = m["delta_sem_ai_f1"]
    
    print(f"| **{m_id}** | {iss1:.4f} | {iss2:.4f} | {diss:+.4f} | {dec1:.4f} | {dec2:.4f} | {ddec:+.4f} | {ai1:.4f} | {ai2:.4f} | {dai:+.4f} |")

print("\nAggregate comparison:")
print(json.dumps(agg, indent=2))
