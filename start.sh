#!/bin/bash
cd "$(dirname "$0")"
kill $(pgrep -f "agentic.web_server") 2>/dev/null
nohup python3 -m agentic.web_server > /tmp/pf.log 2>&1 &
sleep 2
echo "PaperForge → http://$(hostname -I | awk '{print $1}'):5055/paperforge"
