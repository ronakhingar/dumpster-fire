# AWS Multi-Agent Production Setup

Complete guide for deploying multi-agent trading system to AWS EC2.

## Cost Breakdown

```
Monthly Costs:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EC2 t4g.medium (4GB, ARM):        $24.00/month
EBS gp3 30GB:                     $2.40/month
Elastic IP:                       $3.60/month
S3 Backups (~100GB):              $2.30/month
Glacier Backups (~50GB):          $0.20/month
Data Transfer (~20GB):            $1.80/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:                            ~$34/month ($408/year)

First 12 months (Free Tier):      ~$150 saved
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Prerequisites

1. AWS Account
2. AWS CLI installed locally: `brew install awscli`
3. GitHub repository
4. Domain (optional, for HTTPS)

---

## Step 1: Create EC2 Instance

### Via AWS Console:

1. **Go to EC2 Dashboard** → Launch Instance
2. **Name:** `dumpster-fire-trading`
3. **AMI:** Ubuntu Server 22.04 LTS (free tier eligible)
4. **Instance type:**
   - Start: `t4g.small` (2GB, $12/month) - test first
   - Scale to: `t4g.medium` (4GB, $24/month) - when adding agents
5. **Key pair:** Create new or use existing
6. **Network settings:**
   - ✅ Allow SSH (port 22) from your IP
   - ✅ Allow HTTPS (port 443) - optional
7. **Storage:** 30GB gp3 SSD
8. **Launch**

### Via AWS CLI:

```bash
# Create security group
aws ec2 create-security-group \
  --group-name dumpster-fire-sg \
  --description "Security group for trading system"

# Allow SSH
aws ec2 authorize-security-group-ingress \
  --group-name dumpster-fire-sg \
  --protocol tcp \
  --port 22 \
  --cidr YOUR_IP/32

# Launch instance
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type t4g.medium \
  --key-name YOUR_KEY_PAIR \
  --security-groups dumpster-fire-sg \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=dumpster-fire-trading}]'
```

---

## Step 2: Initial Server Setup

SSH into your instance:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
```

### Install Docker & Docker Compose:

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes
exit
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
```

### Install AWS CLI (for backups):

```bash
sudo apt-get install -y awscli
aws configure  # Add your credentials
```

---

## Step 3: Clone Repository

```bash
cd /home/ubuntu
git clone https://github.com/ronakhingar/dumpster-fire.git
cd dumpster-fire
```

### Set up environment variables:

```bash
cp .env.example .env
nano .env
```

Add your keys:
```bash
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
DISCORD_USER_TOKEN=your_token
TRADING_DB_PASSWORD=secure_password
GEMINI_API_KEY=your_key
IBKR_PAPER_USERNAME=your_username
IBKR_PAPER_PASSWORD=your_password
IBKR_PAPER_PORT=4002
```

---

## Step 4: Create S3 Backup Bucket

```bash
# Create bucket
aws s3 mb s3://dumpster-fire-backups --region us-east-1

# Set lifecycle policy for automatic cost optimization
cat > lifecycle-policy.json <<EOF
{
  "Rules": [
    {
      "Id": "daily-to-ia-after-30-days",
      "Status": "Enabled",
      "Prefix": "daily/",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 365
      }
    },
    {
      "Id": "weekly-to-glacier",
      "Status": "Enabled",
      "Prefix": "weekly/",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket dumpster-fire-backups \
  --lifecycle-configuration file://lifecycle-policy.json
```

---

## Step 5: Start Multi-Agent System

```bash
cd /home/ubuntu/dumpster-fire

# Build and start all agents
docker-compose -f docker-compose.multi-agent.yml up -d

# Check status
docker-compose -f docker-compose.multi-agent.yml ps

# View logs
docker-compose -f docker-compose.multi-agent.yml logs -f stock-agent
docker-compose -f docker-compose.multi-agent.yml logs -f futures-agent
```

---

## Step 6: Setup Automated Backups

```bash
# Make backup script executable
chmod +x scripts/backup_to_s3.sh

# Add to crontab (runs daily at 2 AM ET)
crontab -e
```

Add this line:
```
0 2 * * * /home/ubuntu/dumpster-fire/scripts/backup_to_s3.sh >> /home/ubuntu/dumpster-fire/logs/backup.log 2>&1
```

---

## Step 7: Setup GitHub Actions CI/CD

### 1. Create IAM User for GitHub Actions:

```bash
aws iam create-user --user-name github-actions-dumpster-fire

# Attach policy (allows SSM commands)
aws iam attach-user-policy \
  --user-name github-actions-dumpster-fire \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

# Create access keys
aws iam create-access-key --user-name github-actions-dumpster-fire
```

### 2. Install SSM Agent on EC2:

```bash
sudo snap install amazon-ssm-agent --classic
sudo snap start amazon-ssm-agent
```

### 3. Add GitHub Secrets:

Go to: https://github.com/ronakhingar/dumpster-fire/settings/secrets/actions

Add:
- `AWS_ACCESS_KEY_ID` - from step 1
- `AWS_SECRET_ACCESS_KEY` - from step 1
- `EC2_INSTANCE_ID` - your instance ID (i-xxxxx)

### 4. Test Deployment:

```bash
# Push to main branch
git add .
git commit -m "Test automated deployment"
git push origin main
```

GitHub Actions will automatically deploy!

---

## Step 8: Monitoring & Maintenance

### Check Agent Status:

```bash
docker ps
docker logs stock-agent --tail 50
docker logs futures-agent --tail 50
```

### View Trading Activity:

```bash
tail -f journal/agent_cron.log
tail -f logs/discord_bot.log
```

### Restart Specific Agent:

```bash
docker-compose -f docker-compose.multi-agent.yml restart stock-agent
```

### Update Code:

```bash
cd /home/ubuntu/dumpster-fire
git pull origin main
docker-compose -f docker-compose.multi-agent.yml up -d --build
```

---

## Cost Optimization Tips

1. **Use Spot Instances** (save 70%):
   ```bash
   # Create spot request for t4g.medium
   # Only for non-critical testing
   ```

2. **Stop instance nights/weekends** (if not trading 24/7):
   ```bash
   aws ec2 stop-instances --instance-ids i-xxxxx
   ```

3. **Use S3 Intelligent-Tiering** for automatic cost optimization

4. **Monitor with CloudWatch** (free tier: 10 metrics)

---

## Troubleshooting

### IBKR Gateway not connecting:

```bash
# Check VNC (debugging)
ssh -L 5900:localhost:5900 ubuntu@YOUR_EC2_IP
# Then connect via VNC client to localhost:5900
# Password: ibkr_vnc
```

### Out of memory:

```bash
# Check memory usage
docker stats

# Upgrade to larger instance
aws ec2 modify-instance-attribute \
  --instance-id i-xxxxx \
  --instance-type t4g.large
```

### Restore from backup:

```bash
# List backups
aws s3 ls s3://dumpster-fire-backups/daily/ --recursive

# Download and restore
aws s3 cp s3://dumpster-fire-backups/daily/2026/04/01/backup-xxx.tar.gz .
tar -xzf backup-xxx.tar.gz
```

---

## Next Steps

- [ ] Set up CloudWatch alarms for errors
- [ ] Configure Route53 domain (optional)
- [ ] Set up SSL with Let's Encrypt (optional)
- [ ] Add Slack/email notifications
- [ ] Scale to multiple instances (future)
