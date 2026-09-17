# QMSum - dataset package

STATUS: ACQUIRED (full dataset).

232 meetings, 1,810 query-summary pairs, across Academic/Committee/
Product domains. Official train/validation/test splits preserved in
raw/data/. Common-format conversion in processed/ (qmsum_{train,validation,test}.jsonl), produced by
processed/process_qmsum.py.

Fields available: transcript, queries, answers, relevant transcript
spans. NOT available: pre-extracted action items/decisions/issues.

Source: https://github.com/Yale-LILY/QMSum
Citation: Zhong et al. (2021), QMSum, NAACL 2021.
