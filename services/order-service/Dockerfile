FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --chown=node:node shared ./shared
COPY --chown=node:node fixtures ./fixtures
COPY --chown=node:node order-service ./order-service
USER node
EXPOSE 3002
CMD ["node", "order-service/index.js"]
