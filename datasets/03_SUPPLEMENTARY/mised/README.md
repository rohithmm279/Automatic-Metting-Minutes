# MISeD - dataset package

STATUS: ACQUIRED (full dataset).

432 information-seeking dialogs (303 train / 63 validation / 66 test)
grounded in AMI/ICSI meeting transcript segments, plus a fully-manual
WOZ variant (raw/woz/woz.jsonl). Common-format conversion in
processed/mised_{train,validation,test}.jsonl.

CORRECTION vs. original task assumption: meeting IDs follow AMI/ICSI
naming (e.g. ES2004a, Bmr006), not QMSum; each record is self-contained
(embeds its own transcript segments) rather than referencing QMSum.

Source: https://github.com/google-research-datasets/MISeD
Citation: Golany et al. (2024), Findings of EMNLP 2024.
