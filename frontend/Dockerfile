# Use the official Docker Hub image; avoid ECR Public data-quota throttling.
FROM docker.io/library/node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--strictPort"]
