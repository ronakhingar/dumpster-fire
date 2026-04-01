#!/bin/bash
# Automated backup to Google Cloud Storage
# Run daily via cron: 0 2 * * * /home/ubuntu/dumpster-fire/scripts/backup_to_gcs.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backup-$TIMESTAMP.tar.gz"
GCS_BUCKET="dumpster-fire-backups"

cd "$PROJECT_DIR"

echo "$(date): Starting backup to Google Cloud Storage..."

# Create backup archive
tar -czf "$BACKUP_FILE" \
  journal/ \
  data/ \
  logs/*.log \
  .env \
  docker-compose.multi-agent.yml \
  --exclude='journal/*.tmp' \
  --exclude='data/cache/*'

# Upload to GCS with appropriate storage class
# Daily backups → Standard
gsutil cp "$BACKUP_FILE" \
  "gs://$GCS_BUCKET/daily/$(date +%Y/%m/%d)/$BACKUP_FILE"

# Weekly backups → Nearline (30-day minimum, cheaper)
if [ "$(date +%u)" -eq 7 ]; then  # Sunday
  gsutil -h "x-goog-storage-class:NEARLINE" \
    cp "$BACKUP_FILE" \
    "gs://$GCS_BUCKET/weekly/$(date +%Y/%W)/$BACKUP_FILE"
fi

# Monthly backups → Coldline (90-day minimum, cheapest)
if [ "$(date +%d)" -eq 01 ]; then  # First of month
  gsutil -h "x-goog-storage-class:COLDLINE" \
    cp "$BACKUP_FILE" \
    "gs://$GCS_BUCKET/monthly/$(date +%Y/%m)/$BACKUP_FILE"
fi

# Remove local backup file
rm "$BACKUP_FILE"

echo "$(date): Backup completed: $BACKUP_FILE"

# Clean up old daily backups (keep 7 days)
gsutil ls "gs://$GCS_BUCKET/daily/**" \
  | head -n -7 \
  | xargs -I {} gsutil rm {}

echo "$(date): Old backups cleaned up"
