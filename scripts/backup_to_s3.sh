#!/bin/bash
# Automated backup to AWS S3
# Run daily via cron: 0 2 * * * /home/ubuntu/dumpster-fire/scripts/backup_to_s3.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backup-$TIMESTAMP.tar.gz"
S3_BUCKET="dumpster-fire-backups"

cd "$PROJECT_DIR"

echo "$(date): Starting backup to S3..."

# Create backup archive
tar -czf "$BACKUP_FILE" \
  journal/ \
  data/ \
  logs/*.log \
  .env \
  docker-compose.multi-agent.yml \
  --exclude='journal/*.tmp' \
  --exclude='data/cache/*'

# Upload to S3 with appropriate storage class
# Daily backups → S3 Standard
aws s3 cp "$BACKUP_FILE" \
  "s3://$S3_BUCKET/daily/$(date +%Y/%m/%d)/$BACKUP_FILE" \
  --storage-class STANDARD

# Weekly backups → S3 Standard-IA (cheaper for infrequent access)
if [ "$(date +%u)" -eq 7 ]; then  # Sunday
  aws s3 cp "$BACKUP_FILE" \
    "s3://$S3_BUCKET/weekly/$(date +%Y/%W)/$BACKUP_FILE" \
    --storage-class STANDARD_IA
fi

# Monthly backups → Glacier (long-term, cheapest)
if [ "$(date +%d)" -eq 01 ]; then  # First of month
  aws s3 cp "$BACKUP_FILE" \
    "s3://$S3_BUCKET/monthly/$(date +%Y/%m)/$BACKUP_FILE" \
    --storage-class GLACIER
fi

# Remove local backup file
rm "$BACKUP_FILE"

echo "$(date): Backup completed: $BACKUP_FILE"

# Clean up old daily backups (keep 7 days)
aws s3 ls "s3://$S3_BUCKET/daily/" --recursive \
  | awk '{print $4}' \
  | head -n -7 \
  | xargs -I {} aws s3 rm "s3://$S3_BUCKET/{}"

echo "$(date): Old backups cleaned up"
