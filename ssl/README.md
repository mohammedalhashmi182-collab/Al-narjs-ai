# SSL Certificates for alnarjisai.com

Place your SSL certificates in this directory:

- `alnarjisai.com.crt` - Full chain certificate
- `alnarjisai.com.key` - Private key

## Generate with Let's Encrypt (certbot)

```bash
# On your server
sudo certbot certonly --standalone -d alnarjisai.com -d www.alnarjisai.com

# Copy to this directory
sudo cp /etc/letsencrypt/live/alnarjisai.com/fullchain.pem ./ssl/alnarjisai.com.crt
sudo cp /etc/letsencrypt/live/alnarjisai.com/privkey.pem ./ssl/alnarjisai.com.key
sudo chown $USER:$USER ./ssl/*
```

## For Development (Self-signed)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/alnarjisai.com.key \
  -out ssl/alnarjisai.com.crt \
  -subj "/CN=alnarjisai.com"
```

Then add `127.0.0.1 alnarjisai.com www.alnarjisai.com` to `/etc/hosts`