# GPT response fixtures

These four fixtures are byte-for-byte copies of the fresh GPT-6.1 Sol / medium frontend case runs from 25 October 2026. The output directory name contains the planned rerun date; assessment timestamps in the responses preserve the actual date. No scores, outcomes, evidence, execution states, model identities or version fields were edited. Each source remains unchanged. The Attention fixture covers display rounding in both report views.

```json
[
  {
    "fixture": "credibility-attention.json",
    "source": "/Users/qitouda/Desktop/COMP5703/outputs/gpt-rerun-20261026/cases/attention/credibility-final.json",
    "sha256": "1f28ca4762e2f750f0174eec335b9edb7e733aa043251a6dfba3dd2bbba9dcd1",
    "transformation": "None; byte-for-byte copy. Only fixture filename changed."
  },
  {
    "fixture": "credibility-paper-005.json",
    "source": "/Users/qitouda/Desktop/COMP5703/outputs/gpt-rerun-20261026/cases/paper_005/credibility-final.json",
    "sha256": "7d0efbd1facd3cdbe42565423c0a04964ac11f40f739968ca8adae62f9b8430b",
    "transformation": "None; byte-for-byte copy. Only fixture filename changed."
  },
  {
    "fixture": "credibility-lora.json",
    "source": "/Users/qitouda/Desktop/COMP5703/outputs/gpt-rerun-20261026/cases/lora/credibility-final.json",
    "sha256": "9ff9949049b0f71245d57ea30e4da451968429c95576f809bd99956c66887a49",
    "transformation": "None; byte-for-byte copy. Only fixture filename changed."
  },
  {
    "fixture": "quality-paper-005.json",
    "source": "/Users/qitouda/Desktop/COMP5703/outputs/gpt-rerun-20261026/cases/paper_005/quality-final.json",
    "sha256": "4b8e0cab1d7c0c447d2ebfdd298ebb52c79db6b2536b13e69270abc6e0e208aa",
    "transformation": "None; byte-for-byte copy. Only fixture filename changed."
  }
]
```

The fixtures record backend `5a7772c` and frontend `7ba8d32` as the evaluated revisions. This cleanup branch and its offline tests are a later software revision, not an additional model experiment.
