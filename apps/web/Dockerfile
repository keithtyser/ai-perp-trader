FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files and install
COPY package.json package-lock.json* ./
RUN npm install

# Copy config files first
COPY tsconfig.json next.config.js tailwind.config.ts postcss.config.js ./

# Copy source code
COPY app ./app
COPY lib ./lib
COPY components ./components
COPY public ./public

# Build
RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["npm", "start"]
