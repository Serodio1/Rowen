# The page's image (ADR 0009). Built in two stages: the first builds the page
# with Node, the second serves the built files with nginx, so the image has
# neither Node nor the source code.

FROM node:24-alpine AS build

WORKDIR /app

# The packages first, in their own layer: Docker reuses it as long as
# package.json and package-lock.json do not change. .npmrc keeps the same
# protections as on a computer (ADR 0007).
COPY package.json package-lock.json .npmrc ./
RUN npm ci

# Then the code, built into dist/.
COPY . .
RUN npm run build

# The image nginx's makers publish for running nginx as a user with no special
# rights, not as root. Its own command starts nginx, so no CMD is needed.
FROM nginxinc/nginx-unprivileged:1.30-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
