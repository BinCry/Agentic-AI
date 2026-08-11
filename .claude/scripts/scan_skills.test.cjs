#!/usr/bin/env node
/**
 * Regression tests for scan_skills.py catalog generation.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const SCRIPT_PATH = path.join(__dirname, 'scan_skills.py');
const SKILLS_DATA_PATH = path.join(__dirname, 'skills_data.yaml');
const GUIDE_YAML_PATH = path.join(REPO_ROOT, 'guide', 'SKILLS.yaml');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  OK ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`  FAIL ${name}`);
    console.log(`    Error: ${error.message}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

function assertMatch(content, pattern, message) {
  assert(pattern.test(content), message);
}

function resolvePythonCommand() {
  const candidates = process.platform === 'win32'
    ? ['py -3', 'python', 'python3']
    : ['python3', 'python'];

  for (const candidate of candidates) {
    try {
      execSync(`${candidate} --version`, {
        cwd: REPO_ROOT,
        stdio: 'pipe',
        encoding: 'utf-8',
      });
      return candidate;
    } catch {
      // Try the next available Python command.
    }
  }

  throw new Error('No usable Python interpreter found for scan_skills.py');
}

console.log('\nscan_skills.py Regression Tests');

execSync(`${resolvePythonCommand()} "${SCRIPT_PATH}"`, {
  cwd: REPO_ROOT,
  stdio: 'pipe',
  encoding: 'utf-8',
});

const skillsData = fs.readFileSync(SKILLS_DATA_PATH, 'utf-8');
const guideYaml = fs.readFileSync(GUIDE_YAML_PATH, 'utf-8');

test('mcp-builder stays in dev-tools', () => {
  assertMatch(
    skillsData,
    /- name: "mcp-builder"[\s\S]*?category: "dev-tools"/,
    'mcp-builder should be categorized as dev-tools',
  );
});

test('document skills stay under multimedia', () => {
  assertMatch(
    guideYaml,
    /- name: "docx"[\s\S]*?category: "multimedia"/,
    'docx should be categorized as multimedia',
  );
});

test('catalog paths stay portable across platforms', () => {
  assert(!skillsData.includes('\\SKILL.md'), 'skills registry should use forward-slash paths');
  assertMatch(
    skillsData,
    /path: "document-skills\/docx\/SKILL\.md"/,
    'nested skill paths should use POSIX separators',
  );
});

test('block frontmatter descriptions are flattened', () => {
  assert(!guideYaml.includes('description: ">-"'), 'guide catalog should not emit raw block markers');
  assertMatch(
    guideYaml,
    /name: "context-engineering"[\s\S]*?description: "Check context usage limits,/,
    'context-engineering description should be flattened',
  );
  assertMatch(
    guideYaml,
    /name: "excalidraw"[\s\S]*?description: "Create Excalidraw diagrams/,
    'excalidraw description should be flattened',
  );
});

if (failed > 0) {
  console.log(`\nTest Results: ${passed} passed, ${failed} failed`);
  process.exit(1);
}

console.log(`\nTest Results: ${passed} passed, ${failed} failed`);
