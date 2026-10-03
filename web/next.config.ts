import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false, // keep the stage clean
  // Phones on the same Wi-Fi open the dev server by the laptop's network address (multiplayer rooms).
  allowedDevOrigins: ["192.168.*.*", "10.*.*.*", "172.*.*.*"],
};

export default nextConfig;
