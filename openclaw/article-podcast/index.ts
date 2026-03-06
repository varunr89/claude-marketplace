import { existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const PLUGIN_ID = "openclaw-plugin-article-podcast";
const SCRIPTS_DIR = join(__dirname, "skills", "article-podcast", "scripts");
const CONFIG_DIR = join(homedir(), ".openclaw", "plugins", PLUGIN_ID);
const CONFIG_FILE = join(CONFIG_DIR, "config.json");
const JOB_DIR = join(CONFIG_DIR, "jobs");

export default function register(api: any) {
  const config = api.pluginConfig || {};
  const log = api.logger;

  // Write config for Python scripts
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));

  // Create job queue directories
  for (const sub of ["pending", "processing", "completed", "failed"]) {
    mkdirSync(join(JOB_DIR, sub), { recursive: true });
  }

  log.info(`${PLUGIN_ID} loaded, config at ${CONFIG_FILE}`);
}
