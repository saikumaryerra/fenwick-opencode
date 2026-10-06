#!/usr/bin/env bash
# Deploy the committed tree (HEAD) to a Hugging Face Docker Space.
#
# Usage: HF_SPACE=<owner>/<space-name> scripts/deploy_hf_space.sh
#
# Uploads `git archive HEAD` rather than the working directory, so only
# committed, tracked files reach the public Space; .env and .venv never leave
# this machine. `hf upload` stores the .docx data files with Xet, which a plain
# `git push` to the Space would reject as binary.
set -euo pipefail

: "${HF_SPACE:?Set HF_SPACE=<owner>/<space-name>}"

cd "$(git rev-parse --show-toplevel)"

if ! git diff --quiet HEAD --; then
  echo "error: tracked files have uncommitted changes; only HEAD is deployed, so commit first." >&2
  exit 1
fi

commit="$(git rev-parse --short HEAD)"
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT

git archive HEAD | tar -x -C "$build_dir"

hf repo create "$HF_SPACE" --repo-type space --space_sdk docker --exist-ok
# --delete "*" removes Space files that no longer exist in HEAD.
hf upload "$HF_SPACE" "$build_dir" . \
  --repo-type space \
  --delete "*" \
  --commit-message "Deploy $commit"

echo "Deployed $commit to https://huggingface.co/spaces/$HF_SPACE"
echo "Set GROQ_API_KEY under Settings > Variables and secrets if not already set."
