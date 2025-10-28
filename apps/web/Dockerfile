FROM node:20-alpine AS builder

WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN npm ci --legacy-peer-deps || npm install

# Build the app
RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/package.json ./
COPY --from=builder /app/package-lock.json* ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

ENV NODE_ENV=production
ENV PORT=3000

EXPOSE 3000

CMD ["npm", "start"]
