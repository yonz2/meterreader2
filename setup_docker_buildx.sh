# Create a new builder instance (if you haven't already)
docker buildx create --name meterreader-builder --use

# Build for both platforms
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t yonz/meterreader:latest \
    -f Dockerfile \
    --push .
