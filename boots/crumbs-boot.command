#!/bin/bash
BOOT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
"$BOOT_DIR/crumbs-boot.sh" "$@"
result=$?
echo
read -r -p "Press Return to close this window..." _
exit "$result"
