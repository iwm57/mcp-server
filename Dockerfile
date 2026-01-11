# Base image
FROM node:20-alpine

# Working directory
WORKDIR /app

# Install dependencies
COPY package.json .
RUN npm install --production

# Copy app
COPY server.js .

# Expose port
EXPOSE 8000

# Run
CMD ["npm", "start"]
