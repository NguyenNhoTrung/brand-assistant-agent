import next from "eslint-config-next";

const config = [...next, { ignores: [".next/**", "lib/types.gen.ts"] }];

export default config;
