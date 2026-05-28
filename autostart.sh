#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 맥북 자동시작 등록 (부팅 시 서버 자동 실행)
# ═══════════════════════════════════════════════════════════════
# 사용법: chmod +x autostart.sh && ./autostart.sh
# ═══════════════════════════════════════════════════════════════

WORK="$HOME/music_pipeline"
PLIST="$HOME/Library/LaunchAgents/com.music.pipeline.plist"
CAFF_PLIST="$HOME/Library/LaunchAgents/com.music.caffeinate.plist"

# 서버 자동시작
cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.music.pipeline</string>
    <key>ProgramArguments</key>
    <array>
        <string>${WORK}/venv/bin/python</string>
        <string>${WORK}/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${WORK}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${WORK}/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${WORK}/logs/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# 잠자기 방지
cat > "$CAFF_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.music.caffeinate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
launchctl unload "$CAFF_PLIST" 2>/dev/null || true
launchctl load "$CAFF_PLIST"

echo "✅ 자동시작 등록 완료"
echo "   서버: launchctl list | grep music"
echo "   중지: launchctl unload $PLIST"
