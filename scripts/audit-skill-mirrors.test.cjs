#!/usr/bin/env node
/**
 * Regression tests for audit-skill-mirrors.py.
 */

const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');
const SCRIPT_PATH = path.join(__dirname, 'audit-skill-mirrors.py');

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

function resolvePythonInvocation() {
  const candidates = process.platform === 'win32'
    ? [{ command: 'py', args: ['-3'] }, { command: 'python', args: [] }, { command: 'python3', args: [] }]
    : [{ command: 'python3', args: [] }, { command: 'python', args: [] }];

  for (const candidate of candidates) {
    try {
      execFileSync(candidate.command, [...candidate.args, '--version'], {
        cwd: REPO_ROOT,
        stdio: 'pipe',
        encoding: 'utf-8',
      });
      return candidate;
    } catch {
      // Try the next Python command.
    }
  }

  throw new Error('No usable Python interpreter found for audit-skill-mirrors.py');
}

function writeSkill(rootDir, skillId, content) {
  const skillDir = path.join(rootDir, ...skillId.split('/'));
  fs.mkdirSync(skillDir, { recursive: true });
  fs.writeFileSync(path.join(skillDir, 'SKILL.md'), content, 'utf8');
}

function createFixture() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-mirror-audit-'));
  const roots = {
    claude: path.join(tempDir, 'claude', 'skills'),
    codex: path.join(tempDir, 'codex', 'skills'),
    agents: path.join(tempDir, 'agents', 'skills'),
  };

  writeSkill(roots.claude, 'shared-skill', '# Shared\nsame\n');
  writeSkill(roots.codex, 'shared-skill', '# Shared\nsame\n');
  writeSkill(roots.agents, 'shared-skill', '# Shared\nsame\n');

  writeSkill(roots.claude, 'document-skills/docx', '# Nested\nsame\n');
  writeSkill(roots.codex, 'document-skills/docx', '# Nested\nsame\n');

  writeSkill(roots.claude, 'drifted-skill', '# Drift\none\n');
  writeSkill(roots.codex, 'drifted-skill', '# Drift\ntwo\n');

  writeSkill(roots.agents, 'solo-skill', '# Solo\nroot\n');

  return { tempDir, roots };
}

function runAudit(invocation, roots, extraArgs = []) {
  const args = [
    ...invocation.args,
    SCRIPT_PATH,
    '--root', `claude=${roots.claude}`,
    '--root', `codex=${roots.codex}`,
    '--root', `agents=${roots.agents}`,
    ...extraArgs,
  ];

  return execFileSync(invocation.command, args, {
    cwd: REPO_ROOT,
    stdio: 'pipe',
    encoding: 'utf-8',
  });
}

console.log('\naudit-skill-mirrors.py Regression Tests');

const invocation = resolvePythonInvocation();
const fixture = createFixture();

try {
  test('json report classifies mirrored, partial, and drifted skills', () => {
    const report = JSON.parse(runAudit(invocation, fixture.roots, ['--json']));

    assert(report.summary.unique_skills === 4, 'expected 4 unique skills');
    assert(report.summary.fully_mirrored === 1, 'expected 1 fully mirrored skill');
    assert(report.summary.partial_consistent === 1, 'expected 1 partial consistent skill');
    assert(report.summary.partial_drifted === 1, 'expected 1 partial drifted skill');
    assert(report.summary.single_root_only === 1, 'expected 1 single root only skill');
    assert(report.summary.drifted_total === 1, 'expected drifted_total to equal 1');

    const nestedSkill = report.skills.find((skill) => skill.skill === 'document-skills/docx');
    assert(Boolean(nestedSkill), 'expected nested skill to appear in report');
    assert(nestedSkill.status === 'partial-consistent', 'expected nested skill to stay partial-consistent');
  });

  test('fail-on-drift exits non-zero when drift exists', () => {
    const result = spawnSync(
      invocation.command,
      [
        ...invocation.args,
        SCRIPT_PATH,
        '--root', `claude=${fixture.roots.claude}`,
        '--root', `codex=${fixture.roots.codex}`,
        '--root', `agents=${fixture.roots.agents}`,
        '--fail-on-drift',
      ],
      {
        cwd: REPO_ROOT,
        stdio: 'pipe',
        encoding: 'utf-8',
      },
    );

    assert(result.status === 1, `expected exit code 1, got ${result.status}`);
  });
} finally {
  fs.rmSync(fixture.tempDir, { recursive: true, force: true });
}

if (failed > 0) {
  console.log(`\nTest Results: ${passed} passed, ${failed} failed`);
  process.exit(1);
}

console.log(`\nTest Results: ${passed} passed, ${failed} failed`);
