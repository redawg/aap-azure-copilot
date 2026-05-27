#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/_run-playbook.sh" playbooks/aap-create-all-job-templates.yml -e @group_vars/all.yml "$@"
