FROM node:20-alpine

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create app directory
WORKDIR /sandbox

# Copy amala-sandbox runtime
COPY package.json package-lock.json* ./
RUN npm install --production

# Copy runner script
COPY runner.js .

# Create non-root user for security
RUN addgroup -g 1000 sandbox && \
    adduser -u 1000 -G sandbox -s /sbin/nologin sandbox

# Set permissions
RUN chown -R sandbox:sandbox /sandbox && \
    chmod -R 750 /sandbox

# Switch to non-root user
USER sandbox

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/sbin/dumb-init", "--"]

# Default command
CMD ["node", "runner.js"]
