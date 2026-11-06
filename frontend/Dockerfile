# The page's image (ADR 0009). Built in two stages: the first builds the page
# with Node, the second serves the built files with nginx, so the image has
# neither Node nor the source code.

# Each base image is named by its digest (the hash of its contents) as well as
# its tag. A tag moves when its makers publish a new build, so CI's two builds
# of one commit (the Docker job, which tests it, and the Deploy job) could
# start from different bases; a digest never moves (ADR 0016). To take a new
# build (security fixes), change the digest to the one that
#   docker buildx imagetools inspect <the image's name and tag>
# prints as "Digest".

FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS build

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
FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

# Healthy once nginx serves the page (docker compose up --wait waits for it,
# as for the API), with busybox's wget, which Alpine images have.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --start-interval=1s --retries=5 \
    CMD ["wget", "--quiet", "--spider", "http://127.0.0.1:8080/"]
