# ---------- deps ----------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# ---------- build ----------
FROM node:22-alpine AS build
WORKDIR /app
ARG BACKEND_URL=http://backend:8000
ARG NEXT_PUBLIC_SPEECH_LANG=en-US
ARG NEXT_PUBLIC_INSURER_NAME="Al Rajhi Takaful"
ARG NEXT_PUBLIC_INSURER_SHORT="Al Rajhi Takaful"
ENV BACKEND_URL=$BACKEND_URL NEXT_PUBLIC_SPEECH_LANG=$NEXT_PUBLIC_SPEECH_LANG NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_INSURER_NAME=$NEXT_PUBLIC_INSURER_NAME NEXT_PUBLIC_INSURER_SHORT=$NEXT_PUBLIC_INSURER_SHORT
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- run ----------
FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
