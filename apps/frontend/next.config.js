const path = require("path");

const isStandalone = process.env.BUILD_STANDALONE === "true";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  ...(isStandalone
    ? {
        output: "standalone",
        experimental: {
          outputFileTracingRoot: path.join(__dirname, "../../"),
        },
      }
    : {}),
  transpilePackages: ["@finsim/shared-types"],
};

module.exports = nextConfig;
