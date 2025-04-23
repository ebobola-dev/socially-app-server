#!/bin/sh

envsubst '${SERVER_PORT}' \
	< /etc/nginx/nginx.conf.template \
	> /etc/nginx/conf.d/default.conf

echo "Generated nginx config:"
cat /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
