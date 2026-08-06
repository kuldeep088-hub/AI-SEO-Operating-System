/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `pg` is a native-ish Node module; keep it out of the bundler.
  serverExternalPackages: ["pg"],
  env: {
    API_URL: process.env.API_URL ?? "http://localhost:8000",
  },
};
export default nextConfig;
