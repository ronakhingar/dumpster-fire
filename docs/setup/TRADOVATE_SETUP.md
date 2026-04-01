# Tradovate Setup for Cloud Futures Trading

**Why Tradovate > IBKR for cloud automation:**
- ✅ No TWS/Gateway needed (pure REST API)
- ✅ No VNC/display required
- ✅ No daily disconnects
- ✅ No 2FA authentication headaches
- ✅ Better documentation
- ✅ Lower commissions ($0.25 vs $0.85 per contract)
- ✅ Free market data
- ✅ Cloud-native architecture

---

## Step 1: Create Tradovate Account

### Demo Account (Free Testing):

1. **Go to:** https://trader.tradovate.com/
2. **Click:** "Try Demo"
3. **Sign up** with email
4. **Get:** $100,000 paper trading account instantly
5. **No credit card required**

### Live Account (Real Trading):

1. **Go to:** https://trader.tradovate.com/welcome
2. **Click:** "Open Live Account"
3. **Fund minimum:** $500 (micro futures)
4. **Verification:** 1-2 business days

---

## Step 2: Get API Credentials

### 1. Generate API Key:

```
1. Log into Tradovate web platform
2. Go to: Settings → API Keys
3. Click: "Generate New Key"
4. Name: "dumpster-fire-trading"
5. Copy:
   - API Key (username)
   - API Secret (password)
   - Account ID
```

### 2. Add to .env:

```bash
# Tradovate Futures Trading
TRADOVATE_API_KEY=your_api_key_here
TRADOVATE_API_SECRET=your_api_secret_here
TRADOVATE_ACCOUNT_ID=your_account_id
TRADOVATE_DEMO=true  # Set to false for live trading
```

---

## Step 3: Test Connection Locally

```bash
# Install dependencies
pip install requests websocket-client

# Test Tradovate connection
python3 futures/tradovate_client.py
```

**Expected output:**
```
✓ Authenticated with Tradovate (demo=True)
✓ Tradovate client initialized
  Account: Demo Account
  Balance: $100,000.00
  Positions: 0
  Open orders: 0
```

---

## Step 4: Deploy to Cloud

### Update .env on EC2/GCP:

```bash
# SSH into your instance
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_INSTANCE_IP

# Edit .env
cd /home/ubuntu/dumpster-fire
nano .env

# Add Tradovate credentials (same as Step 2)
```

### Deploy with Docker Compose:

```bash
# Use Tradovate-specific compose file
docker-compose -f docker-compose.tradovate.yml up -d

# Check logs
docker logs futures-agent -f
```

**You should see:**
```
✓ Authenticated with Tradovate (demo=True)
✓ Futures agent started
  Monitoring: MES, MNQ
  Interval: 2 minutes
```

---

## Supported Contracts

### Micro Futures (Low Margin):

| Symbol | Name | Margin (approx) | Point Value |
|--------|------|-----------------|-------------|
| **MES** | Micro E-mini S&P 500 | $1,100 | $5/point |
| **MNQ** | Micro E-mini Nasdaq 100 | $1,700 | $2/point |
| **MYM** | Micro E-mini Dow | $700 | $0.50/point |
| **M2K** | Micro E-mini Russell 2000 | $800 | $5/point |
| **MGC** | Micro Gold | $800 | $1/point |
| **MCL** | Micro Crude Oil | $500 | $0.10/point |

### Full-Sized Futures (High Margin):

| Symbol | Name | Margin (approx) | Point Value |
|--------|------|-----------------|-------------|
| **ES** | E-mini S&P 500 | $11,000 | $50/point |
| **NQ** | E-mini Nasdaq 100 | $17,000 | $20/point |
| **YM** | E-mini Dow | $7,000 | $5/point |
| **RTY** | E-mini Russell 2000 | $8,000 | $50/point |

**Recommendation: Start with MES/MNQ (micro contracts)**

---

## Commission Pricing

### Small Plan (No Monthly Fee):
```
✅ $0 monthly fee
✅ $0.85 per contract per side
Example: 100 contracts/month = $85
Good for: <83 trades/month
```

### Standard Plan (Recommended):
```
✅ $49 monthly fee
✅ $0.59 per contract per side
Example: 100 contracts/month = $49 + $59 = $108
Break-even: 83 contracts/month
Good for: 83-250 trades/month
```

### Professional Plan:
```
✅ $149 monthly fee
✅ $0.25 per contract per side
Example: 100 contracts/month = $149 + $25 = $174
Break-even: 248 contracts/month
Good for: >250 trades/month
```

**Start with Small plan, switch to Standard if you exceed 83 trades/month.**

---

## Tradovate vs IBKR Cost Comparison

### Per Month (100 contracts):

```
IBKR:
- Monthly minimum: $10
- Data fees: $10
- Commissions (100 × $0.85): $85
Total: $105/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tradovate (Small):
- Monthly fee: $0
- Data fees: $0
- Commissions (100 × $0.85): $85
Total: $85/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Savings: $20/month ($240/year)
```

---

## Cloud Resource Savings

### With IBKR Gateway:

```
EC2 t4g.medium (4GB):           $24/month
EBS 30GB:                       $2.40/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:                          $26.40/month

RAM breakdown:
- IBKR Gateway:     300MB
- Stock agent:      200MB
- Futures agent:    200MB
- PostgreSQL:       150MB
- Discord:          100MB
- System:           300MB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:              1.25GB (need 2GB minimum)
```

### With Tradovate API:

```
EC2 t4g.small (2GB):            $12/month ← Half the cost!
EBS 30GB:                       $2.40/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:                          $14.40/month

RAM breakdown:
- Stock agent:      200MB
- Futures agent:    200MB (no Gateway!)
- PostgreSQL:       150MB
- Discord:          100MB
- System:           300MB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:              950MB (2GB instance is plenty)
```

**Cloud savings: $12/month ($144/year) by switching to Tradovate!**

---

## Combined Annual Savings

```
Commission savings:      $240/year
Cloud instance savings:  $144/year
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total savings:          $384/year
```

**Tradovate is literally cheaper AND better for cloud automation.**

---

## API Features

### Order Types Supported:
- ✅ Market orders
- ✅ Limit orders
- ✅ Stop orders
- ✅ Stop-limit orders
- ✅ Bracket orders (entry + stop + target in one)
- ✅ OCO (One-Cancels-Other)
- ✅ Trailing stops

### Real-time Data:
- ✅ WebSocket streaming quotes
- ✅ Level 1 market data (free)
- ✅ DOM (Depth of Market)
- ✅ Historical bars

### Account Management:
- ✅ Real-time positions
- ✅ Account balance
- ✅ P&L tracking
- ✅ Order status updates
- ✅ Fill notifications

---

## Migration from IBKR

### What Changes:

**Remove:**
```yaml
# docker-compose.yml
ibkr-gateway:          # Delete entire service
  image: ghcr.io/gnzsnz/ib-gateway:stable
  ...
```

**Add:**
```bash
# .env
TRADOVATE_API_KEY=xxx
TRADOVATE_API_SECRET=xxx
TRADOVATE_ACCOUNT_ID=xxx
```

**Update:**
```python
# futures/futures_agent.py
# OLD:
from ibkr_executor import IBKRExecutor

# NEW:
from futures.tradovate_client import create_client
```

### What Stays the Same:

- ✅ All your analysis code (analyze.py, indicator_engine.py)
- ✅ Signal detection logic
- ✅ A+ scoring system
- ✅ Discord integration
- ✅ Learning system
- ✅ Journal/logging

**Only the execution layer changes - everything else is identical.**

---

## Testing Checklist

### Before Going Live:

- [ ] Test authentication on demo
- [ ] Place test market order
- [ ] Place test bracket order
- [ ] Verify positions display correctly
- [ ] Test order cancellation
- [ ] Verify P&L tracking
- [ ] Run for 1 week on demo
- [ ] Switch to live with small size

---

## Troubleshooting

### "Authentication failed":
```bash
# Check credentials
echo $TRADOVATE_API_KEY
echo $TRADOVATE_API_SECRET

# Verify they match Tradovate dashboard
# Settings → API Keys
```

### "Contract not found":
```python
# Ensure correct symbol format
MES  ✅ (correct)
MESU4 ❌ (specific contract - use root symbol)
/MES ❌ (TradingView format - use Tradovate format)
```

### "Insufficient margin":
```bash
# Check account balance
python3 -c "
from futures.tradovate_client import create_client
client = create_client()
account = client.get_account()
print(f'Balance: \${account.get(\"cashBalance\"):,.2f}')
"

# MES requires ~$1,100 margin
# MNQ requires ~$1,700 margin
```

---

## Resources

- **Official API Docs:** https://api.tradovate.com/
- **Python Examples:** https://github.com/tradovate/example-api-python
- **WebSocket Docs:** https://api.tradovate.com/#section/WebSocket-API
- **Support:** support@tradovate.com
- **Trading Hours:** https://www.tradovate.com/trading-hours/

---

## Next Steps

1. ✅ Create Tradovate demo account
2. ✅ Get API credentials
3. ✅ Test locally with `tradovate_client.py`
4. ✅ Update .env with credentials
5. ✅ Deploy to cloud with `docker-compose.tradovate.yml`
6. ✅ Test on demo for 1 week
7. ✅ Switch to live account

**You're now ready for professional cloud futures trading! 🚀**
