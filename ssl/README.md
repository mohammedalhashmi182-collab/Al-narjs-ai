# SSL Certificates for karmaai.online

Place your SSL certificates in this directory:

- `karmaai.online.crt` - Full chain certificate
- `karmaai.online.key` - Private key

## Generate with Let's Encrypt (certbot)

```bash
# On your server
sudo certbot certonly --standalone -d karmaai.online -d www.karmaai.online

# Copy to this directory
sudo cp /etc/letsencrypt/live/karmaai.online/fullchain.pem ./ssl/karmaai.online.crt
sudo cp /etc/letsencrypt/live/karmaai.online/privkey.pem ./ssl/karmaai.online.key
sudo chown $USER:$USER ./ssl/*
```

## For Development (Self-signed)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/karmaai.online.key \
  -out ssl/karmaai.online.crt \
  -subj "/CN=karmaai.online"
```

Then add `127.0.0.1 karmaai.online www.karmaai.online` to `/etc/hosts`