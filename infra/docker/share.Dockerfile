FROM node:latest

WORKDIR /srv/share

COPY package.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 4000
CMD ["node", "src/server.js"]
