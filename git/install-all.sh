#!/bin/sh
#
# Note: keep this script idempotent. It may be run multiple times.

set -eu

write_file_x() {
  >"$1" cat -
  chmod +x "$1"
}

write_file_x .git/hooks/pre-commit <<EOF
#!/bin/sh
exec git/pre-commit --from-git
EOF
