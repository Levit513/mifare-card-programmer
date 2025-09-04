# Custom Domain Setup for 513solutions.com/513programmer

## Railway Custom Domain Configuration

### Step 1: Add Custom Domain in Railway
1. Go to your Railway project dashboard
2. Navigate to **Settings** → **Domains**
3. Click **Add Domain**
4. Enter: `513solutions.com`
5. Railway will provide you with DNS records to configure

### Step 2: DNS Configuration
Add these DNS records to your 513solutions.com domain:

**For Railway (recommended approach):**
```
Type: CNAME
Name: 513programmer (or @)
Value: [Railway-provided-domain].up.railway.app
TTL: 300
```

**Alternative - A Record:**
```
Type: A
Name: 513programmer
Value: [Railway-provided-IP]
TTL: 300
```

### Step 3: Subdirectory Configuration
The app is now configured to work at `/513programmer` path:
- Main URL: `https://513solutions.com/513programmer`
- Admin login: `https://513solutions.com/513programmer/login`
- Dashboard: `https://513solutions.com/513programmer/admin`

### Step 4: SSL Certificate
Railway will automatically provision SSL certificates for your custom domain.

### Step 5: Environment Variables
Set in Railway dashboard:
```
FLASK_HOST=0.0.0.0
PORT=8080
SECRET_KEY=[generate-secure-key]
```

### Alternative: Subdomain Approach
If you prefer a subdomain instead:
1. Use `mifare.513solutions.com` or `programmer.513solutions.com`
2. Add CNAME record pointing to Railway domain
3. Remove APPLICATION_ROOT configuration from app.py

### Verification
After DNS propagation (5-60 minutes):
- Test: `https://513solutions.com/513programmer`
- Admin login: `admin` / `admin123`

### Troubleshooting
- Check DNS propagation: `nslookup 513solutions.com`
- Verify Railway domain mapping in dashboard
- Check Railway logs for any routing issues
