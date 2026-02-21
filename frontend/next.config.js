/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/proxy/:path*', destination: 'http://localhost:8000/:path*' },
    ];
  },
};

module.exports = nextConfig;
