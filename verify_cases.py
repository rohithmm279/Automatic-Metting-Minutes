import json
from pathlib import Path

ROOT = Path(r"r:\S5 mini datasets")
TRANSCRIPTS = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "transcripts"
GROUND_TRUTH = ROOT / "datasets" / "01_PRIMARY" / "student_club" / "ground_truth"

ranges = [
    ("SC001–SC010", 1, 10),
    ("SC011–SC020", 11, 20),
    ("SC021–SC030", 21, 30),
    ("SC031–SC040", 31, 40),
    ("SC041–SC050", 41, 50),
    ("SC051–SC060", 51, 60),
    ("SC061–SC070", 61, 70),
]

print("| Range | Available | Ground Truth | Ready |")
print("| :--- | :---: | :---: | :---: |")

all_ready = True
for label, start, end in ranges:
    avail_count = 0
    gt_count = 0
    ready_count = 0
    for i in range(start, end + 1):
        m_id = f"SC{i:03d}"
        t_path = TRANSCRIPTS / f"{m_id}.txt"
        g_path = GROUND_TRUTH / f"{m_id}.json"
        
        t_ok = t_path.exists() and len(t_path.read_text(encoding="utf-8").strip()) > 0
        g_ok = False
        if g_path.exists():
            try:
                with g_path.open(encoding="utf-8") as f:
                    g_data = json.load(f)
                    if isinstance(g_data, dict):
                        g_ok = True
            except Exception:
                pass
        
        if t_ok:
            avail_count += 1
        if g_ok:
            gt_count += 1
        if t_ok and g_ok:
            ready_count += 1
            
    status = "Yes" if ready_count == (end - start + 1) else f"Partial ({ready_count}/10)"
    if ready_count != (end - start + 1):
        all_ready = False
    print(f"| {label} | {avail_count}/10 | {gt_count}/10 | {status} |")

print("\nOverall 70 readiness:", "100% Ready (70/70)" if all_ready else "Some missing")
