FROM mcr.microsoft.com/playwright:v1.62.1-noble

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

EXPOSE 8200

CMD ["npm", "start"]
