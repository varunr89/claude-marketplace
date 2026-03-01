import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";
import { parse as parseYaml } from "yaml";

const ROOT = process.argv[2] || ".";
let errors: string[] = [];
let warnings: string[] = [];

function extractFrontmatter(content: string): Record<string, unknown> | null {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  try {
    const processed = match[1].replace(
      /^(\w+):\s+(.+)$/gm,
      (line, key, val) => {
        if (/[{}\[\]]/.test(val) && !val.startsWith('"') && !val.startsWith("'")) {
          return `${key}: "${val.replace(/"/g, '\\"')}"`;
        }
        return line;
      }
    );
    return parseYaml(processed) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function validatePluginJson(pluginDir: string): void {
  const pjPath = join(pluginDir, ".claude-plugin", "plugin.json");
  if (!existsSync(pjPath)) {
    errors.push(`${pluginDir}: missing .claude-plugin/plugin.json`);
    return;
  }
  try {
    const pj = JSON.parse(readFileSync(pjPath, "utf-8"));
    for (const field of ["name", "version", "description"]) {
      if (!pj[field]) errors.push(`${pjPath}: missing required field "${field}"`);
    }
  } catch (e) {
    errors.push(`${pjPath}: invalid JSON`);
  }
}

function validateSkills(pluginDir: string): void {
  const skillsDir = join(pluginDir, "skills");
  if (!existsSync(skillsDir)) return;
  for (const entry of readdirSync(skillsDir)) {
    const skillDir = join(skillsDir, entry);
    if (!statSync(skillDir).isDirectory()) {
      warnings.push(`${skillsDir}/${entry}: skill should be a directory, not a file`);
      continue;
    }
    const skillMd = join(skillDir, "SKILL.md");
    if (!existsSync(skillMd)) {
      errors.push(`${skillDir}: missing SKILL.md`);
      continue;
    }
    const fm = extractFrontmatter(readFileSync(skillMd, "utf-8"));
    if (!fm) {
      errors.push(`${skillMd}: missing or invalid YAML frontmatter`);
      continue;
    }
    if (!fm.name) errors.push(`${skillMd}: frontmatter missing "name"`);
    if (!fm.description && !fm.when_to_use) {
      errors.push(`${skillMd}: frontmatter needs "description" or "when_to_use"`);
    }
  }
}

function validateCommands(pluginDir: string): void {
  const cmdsDir = join(pluginDir, "commands");
  if (!existsSync(cmdsDir)) return;
  for (const file of readdirSync(cmdsDir).filter((f) => f.endsWith(".md"))) {
    const cmdPath = join(cmdsDir, file);
    const fm = extractFrontmatter(readFileSync(cmdPath, "utf-8"));
    if (!fm) {
      errors.push(`${cmdPath}: missing or invalid YAML frontmatter`);
      continue;
    }
    if (!fm.description) errors.push(`${cmdPath}: frontmatter missing "description"`);
  }
}

function validateMarketplace(): void {
  const mjPath = join(ROOT, ".claude-plugin", "marketplace.json");
  if (!existsSync(mjPath)) {
    errors.push("Missing .claude-plugin/marketplace.json");
    return;
  }
  try {
    const mj = JSON.parse(readFileSync(mjPath, "utf-8"));
    if (!mj.name) errors.push("marketplace.json: missing name");
    if (!mj.plugins || !Array.isArray(mj.plugins)) {
      errors.push("marketplace.json: missing or invalid plugins array");
      return;
    }
    const names = new Set<string>();
    for (const plugin of mj.plugins) {
      if (names.has(plugin.name)) {
        errors.push(`marketplace.json: duplicate plugin name "${plugin.name}"`);
      }
      names.add(plugin.name);
      if (typeof plugin.source === "string") {
        const localPath = join(ROOT, plugin.source);
        if (!existsSync(localPath)) {
          errors.push(`marketplace.json: local path "${plugin.source}" does not exist`);
        }
      }
    }
  } catch {
    errors.push("marketplace.json: invalid JSON");
  }
}

// Collision check: duplicate skill names across plugins
function checkCollisions(): void {
  const pluginsDir = join(ROOT, "plugins");
  if (!existsSync(pluginsDir)) return;
  const skillNames = new Map<string, string>();
  for (const entry of readdirSync(pluginsDir)) {
    const pluginDir = join(pluginsDir, entry);
    if (!statSync(pluginDir).isDirectory()) continue;
    const skillsDir = join(pluginDir, "skills");
    if (!existsSync(skillsDir)) continue;
    for (const skillEntry of readdirSync(skillsDir)) {
      const skillDir = join(skillsDir, skillEntry);
      if (!statSync(skillDir).isDirectory()) continue;
      const skillMd = join(skillDir, "SKILL.md");
      if (!existsSync(skillMd)) continue;
      const fm = extractFrontmatter(readFileSync(skillMd, "utf-8"));
      if (fm && fm.name) {
        const name = fm.name as string;
        if (skillNames.has(name)) {
          errors.push(`Skill name collision: "${name}" in ${entry} and ${skillNames.get(name)}`);
        }
        skillNames.set(name, entry);
      }
    }
  }
}

// Main
validateMarketplace();
const pluginsDir = join(ROOT, "plugins");
if (existsSync(pluginsDir)) {
  for (const entry of readdirSync(pluginsDir)) {
    const pluginDir = join(pluginsDir, entry);
    if (!statSync(pluginDir).isDirectory()) continue;
    validatePluginJson(pluginDir);
    validateSkills(pluginDir);
    validateCommands(pluginDir);
  }
}
checkCollisions();

if (warnings.length > 0) {
  console.log("\nWarnings:");
  warnings.forEach((w) => console.log(`  WARNING: ${w}`));
}
if (errors.length > 0) {
  console.log("\nErrors:");
  errors.forEach((e) => console.log(`  ERROR: ${e}`));
  process.exit(1);
} else {
  const pluginCount = existsSync(pluginsDir) ? readdirSync(pluginsDir).filter(e => statSync(join(pluginsDir, e)).isDirectory()).length : 0;
  console.log(`Validation passed. Checked ${pluginCount} plugins.`);
}
