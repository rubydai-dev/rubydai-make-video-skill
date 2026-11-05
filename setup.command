#!/bin/bash
# macOS: double-click to install the skill. Runs setup.sh, then keeps the window open.
bash "$(dirname "$0")/setup.sh"
status=$?
echo
read -r -p "Press Enter to close..."
exit "$status"
