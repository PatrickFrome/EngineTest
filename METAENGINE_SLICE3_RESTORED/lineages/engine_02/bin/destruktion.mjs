#!/usr/bin/env node

import { main } from "../src/cli.mjs";

main(process.argv.slice(2)).then(
  (code) => {
    process.exitCode = code;
  },
  (error) => {
    console.error(`FATAL: ${error.stack || error.message}`);
    process.exitCode = 2;
  },
);
