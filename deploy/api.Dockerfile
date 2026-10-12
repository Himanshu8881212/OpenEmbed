# API + workbench (Next.js). NEXT_PUBLIC_* values are compiled into the browser bundle, so pass them at build time.
FROM node:26-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_KB_OIDC_ISSUER
ARG NEXT_PUBLIC_KB_OIDC_WEB_CLIENT_ID=kb-web
RUN rm -f .env && npx next build

FROM node:26-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY --from=build /app/.next ./.next
COPY --from=build /app/scripts ./scripts
COPY --from=build /app/db ./db
COPY --from=build /app/cli ./cli
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
