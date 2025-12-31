FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
# Expose port 3000
EXPOSE 3000
# Start Vite with --host to expose to network
CMD ["npm", "run", "dev", "--", "--host"]