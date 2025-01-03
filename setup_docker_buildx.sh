# Create a new builder instance (if you haven't already)
docker buildx create --name meterreader-builder --use

# Build for both platforms
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t yonz/meterreader:latest \
    -f Dockerfile \
    --push .


docker personal access token: login -u yonz
dckr_pat_ivO-DvQXeOXAyfAYLG5nQTr8LHA


CloudFlare API: 7d5WaUtkBjspzzyEVZ5FNjip6s-G_ETLr66F5v8v
