#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
smoke_test_api.sh is deprecated.

Iteration 04 removed the old document RAG, /ingest, /search, and chat stream
routes. Use the education data QA smoke suite instead:

  SMOKE_STAGE=chat ./knowledge/tests/smoke_test_data_qa.sh
  SMOKE_STAGE=visual ./knowledge/tests/smoke_test_data_qa.sh
  SMOKE_STAGE=e2e ./knowledge/tests/smoke_test_data_qa.sh
EOF
