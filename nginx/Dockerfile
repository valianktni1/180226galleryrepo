FROM nginx:alpine

# nginx secure_link module is built-in to the official image
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set the secure_link secret via environment variable
# This will be replaced at runtime
CMD ["/bin/sh", "-c", "envsubst '$$NGINX_VIDEO_SECRET' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp && mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
