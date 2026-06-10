#!/bin/sh
# Replace the placeholder with the actual secret from env var
sed -i "s|__NGINX_VIDEO_SECRET__|${NGINX_VIDEO_SECRET}|g" /etc/nginx/conf.d/default.conf
exec "$@"
