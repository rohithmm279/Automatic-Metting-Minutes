import json
from pathlib import Path

ROOT = Path(r"r:\S5 mini datasets")
with open(ROOT / "qwen_eval_SC001_SC070_raw.json", "r", encoding="utf-8") as f:
    data = json.load(f)

per_meeting = data["per_meeting"]

# Sort by AI F1
ai_worst = sorted(per_meeting, key=lambda x: x.get("sem_ai_f1", 0.0))[:5]
# Sort by Dec F1
dec_worst = sorted(per_meeting, key=lambda x: x.get("sem_dec_f1", 0.0))[:5]
# Sort by Iss F1
iss_worst = sorted(per_meeting, key=lambda x: x.get("sem_iss_f1", 0.0))[:5]

print("--- 5 LOWEST ACTION ITEM F1 ---")
for m in ai_worst:
    print(f"Meeting {m['meeting_id']} - Sem F1: {m.get('sem_ai_f1')}")
    print(f"  Pred tasks: {m.get('pred_tasks')}")
    print(f"  GT tasks:   {m.get('gt_tasks')}")

print("\n--- 5 LOWEST DECISION F1 ---")
for m in dec_worst:
    print(f"Meeting {m['meeting_id']} - Sem F1: {m.get('sem_dec_f1')}")
    print(f"  Pred decs: {m.get('pred_decs')}")
    print(f"  GT decs:   {m.get('gt_decs')}")

print("\n--- 5 LOWEST UNRESOLVED ISSUE F1 ---")
for m in iss_worst:
    print(f"Meeting {m['meeting_id']} - Sem F1: {m.get('sem_iss_f1')}")
    print(f"  Pred issues: {m.get('pred_issues')}")
    print(f"  GT issues:   {m.get('gt_issues')}")
