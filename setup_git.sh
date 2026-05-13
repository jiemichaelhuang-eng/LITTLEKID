#!/usr/bin/env bash
# One-shot: clean up any sandbox-leftover .git, init, commit, push, and
# create Michael + Andy working branches.
#
# Usage:
#   1. Edit REMOTE_URL below.
#   2. Open Terminal on your Mac and run:
#        cd ~/ROBOTTT/ROBOT/companion-robot
#        chmod +x setup_git.sh
#        ./setup_git.sh
set -euo pipefail

# ⬇️ EDIT ME — paste your repo URL here, e.g.
#   https://github.com/michaelhuang/companion-robot.git
#   git@github.com:michaelhuang/companion-robot.git
REMOTE_URL="https://github.com/jiemichaelhuang-eng/LITTLEKID.git"

if [[ -z "$REMOTE_URL" ]]; then
  echo "✗ Edit setup_git.sh and set REMOTE_URL to your GitHub repo URL first."
  exit 1
fi

# 1. Wipe any leftover .git from the Cowork sandbox attempt.
if [[ -d .git ]]; then
  echo "→ removing stale .git folder"
  rm -rf .git
fi

# 2. Init a fresh repo on main.
echo "→ git init"
git init -b main
git config user.email "michael.huang@bassunimelb.com"
git config user.name  "Michael"

# 3. First commit.
git add -A
git commit -m "Initial scaffold: hardware + brain + display + main async glue

Folder layout matches section 3 of the project plan. All modules are
starter stubs that wire up the agreed interface contract:

  hardware.servos.set_head(pan_deg, tilt_deg)
  display.eyes.render(state)
  brain.chat.respond(user_text, context) -> (text, emotion, action)

mediapipe / picamera2 / pygame degrade gracefully when absent so the
brain modules run on a laptop for dev."

# 4. Push main.
git remote add origin "$REMOTE_URL"
git push -u origin main

# 5. Create + push the two long-lived working branches.
git branch michael/hardware
git branch andy/brain
git push -u origin michael/hardware
git push -u origin andy/brain

echo
echo "✓ Done. Repo pushed with branches: main, michael/hardware, andy/brain"
echo "  $REMOTE_URL"
