# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /workspace

COPY pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json ./frontend/package.json
RUN pnpm install --filter @mairry/web... --frozen-lockfile

FROM base AS development
WORKDIR /workspace/frontend
COPY frontend/ ./
EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

FROM base AS builder
COPY frontend/ ./frontend/
WORKDIR /workspace/frontend
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN pnpm build

FROM node:22-alpine AS production
ENV NODE_ENV=production
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /workspace
COPY --from=builder /workspace/node_modules ./node_modules
COPY --from=builder /workspace/frontend/node_modules ./frontend/node_modules
COPY --from=builder /workspace/frontend/package.json ./frontend/package.json
COPY --from=builder /workspace/frontend/.next ./frontend/.next
WORKDIR /workspace/frontend
EXPOSE 3000
CMD ["pnpm", "start", "--hostname", "0.0.0.0", "--port", "3000"]

