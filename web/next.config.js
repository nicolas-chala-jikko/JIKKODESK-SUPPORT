/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://api:8000/api/:path*' }
    ]
  },
  experimental: { typedRoutes: false }
}
module.exports = nextConfig
