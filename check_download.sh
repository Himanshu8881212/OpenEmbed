#!/bin/bash
# Script to check ImageBind model download progress

TARGET_SIZE=4800000000  # 4.47 GB in bytes (approximate)
FILE_PATH=".checkpoints/imagebind_huge.pth"

echo "======================================"
echo "ImageBind Model Download Status"
echo "======================================"
echo ""

if [ ! -f "$FILE_PATH" ]; then
    echo "❌ File not found: $FILE_PATH"
    echo "   Download may not have started yet."
    exit 1
fi

# Get current file size
CURRENT_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null)
CURRENT_MB=$((CURRENT_SIZE / 1024 / 1024))
TARGET_MB=$((TARGET_SIZE / 1024 / 1024))

# Calculate percentage
PERCENT=$((CURRENT_SIZE * 100 / TARGET_SIZE))

echo "Downloaded: ${CURRENT_MB} MB / ${TARGET_MB} MB"
echo "Progress: ${PERCENT}%"
echo ""

# Progress bar
BAR_LENGTH=50
FILLED=$((PERCENT * BAR_LENGTH / 100))
EMPTY=$((BAR_LENGTH - FILLED))

printf "["
printf "%${FILLED}s" | tr ' ' '='
printf "%${EMPTY}s" | tr ' ' '-'
printf "] ${PERCENT}%%\n"

echo ""

if [ $CURRENT_SIZE -ge $TARGET_SIZE ]; then
    echo "✅ Download complete!"
    echo "   You can now test the application."
else
    REMAINING=$((TARGET_SIZE - CURRENT_SIZE))
    REMAINING_MB=$((REMAINING / 1024 / 1024))
    echo "⏳ Remaining: ${REMAINING_MB} MB"
    echo ""
    echo "To monitor in real-time, run:"
    echo "  watch -n 5 '$0'"
fi

echo ""
echo "======================================"
