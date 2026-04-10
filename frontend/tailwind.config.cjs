/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx,jsx,js}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Montserrat", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        purple: "#6641ed",
        blue: "#79bcf7",
        pink: "#ff47ac",
        dark: "#0f172a",
      },
      backgroundImage: {
        "brand-gradient":
          "linear-gradient(135deg, #6641ed 0%, #79bcf7 40%, #ff47ac 100%)",
      },
      borderRadius: {
        lg: "0.75rem",
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
