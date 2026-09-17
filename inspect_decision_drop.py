import json
from pathlib import Path

ROOT = Path(r"r:\S5 mini datasets")
with open(ROOT / "qwen_eval_prompt_v2_affected_raw.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for m in data["per_meeting"]:
    if m["meeting_id"] in ["SC016", "SC033", "SC043", "SC049"]:
        print(f"=== {m['meeting_id']} ===")
        print("GT decisions:  ", m["gt_decs"])
        print("V1 decisions:  ", m["v1_pred_decs"], "F1:", m["v1_sem_dec_f1"])
        print("V2 decisions:  ", m["v2_pred_decs"], "F1:", m["sem_dec_f1"])
        print("V1 issues:     ", m["v1_pred_issues"])
        print("V2 issues:     ", m["v2_pred_issues"])
