#!/bin/bash
echo "🚀 Deploying API to Vercel..."

# Install Vercel CLI if not installed
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI..."
    npm install -g vercel
fi

# Deploy to Vercel
echo "Deploying..."
vercel --prod --yes

echo "✅ Deployment complete!"
