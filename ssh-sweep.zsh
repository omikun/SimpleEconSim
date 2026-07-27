#!/bin/zsh

# --- CONFIGURATION ---
# Adjust these to your LAN
SUBNET="192.168.1"        # e.g. 192.168.0 or 10.0.0
USER="omi"      # your SSH username on the remote Mac
PORT="22"                 # or 2222 if you changed SSH port
TIMEOUT=2                 # seconds to wait for connection

# --- SCRIPT BEGINS ---
if [[ -z "$SUBNET" || -z "$USER" ]]; then
  echo "Error: SUBNET and USER must be set."
  exit 1
fi

echo "Scanning $SUBNET.x …"

for i in {1..254}; do
  IP="$SUBNET.$i"
  # Quiet ping, just to see if it's nominally alive
  ping -c 1 -W 0.1 "$IP" &>/dev/null || continue

  echo -n "Trying $IP … "

  if ssh -o ConnectTimeout=$TIMEOUT \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -p "$PORT" \
      "$USER@$IP" "exit" 2>/dev/null; then
    echo "✅ Success"
  else
    echo "❌ Failed"
  fi
done

echo "Done."
