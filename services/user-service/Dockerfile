FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --chown=node:node shared ./shared
COPY --chown=node:node fixtures ./fixtures
COPY --chown=node:node user-service ./user-service
USER node
EXPOSE 3001
CMD ["node", "user-service/index.js"]
