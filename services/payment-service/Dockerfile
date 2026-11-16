FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --chown=node:node shared ./shared
COPY --chown=node:node fixtures ./fixtures
COPY --chown=node:node payment-service ./payment-service
USER node
EXPOSE 3003
CMD ["node", "payment-service/index.js"]
