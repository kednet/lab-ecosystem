/**
 * Chief Agent — agent scaffold.
 *
 * Создание скелета нового агента на Kednet через WebSocket.
 * Chief отправляет Kednet-агенту команду 'scaffold', Kednet-агент
 * создаёт папку + agent.py + requirements.txt + README.md и возвращает
 * список созданных файлов.
 *
 * Также пишет в локальный registry (in-memory REGISTRY array).
 */
'use strict';

const fs = require('fs');
const path = require('path');
const wsHub = require('../ws/hub');
const log = require('../util/logger').make('scaffold');

const TEMPLATES = {
  subprocess: SUBPROCESS_TEMPLATE,
  http: HTTP_TEMPLATE,
  remote: REMOTE_TEMPLATE
};

const SUBPROCESS_TEMPLATE = `# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (subprocess transport).
# Chief (VPS) spawns this script via .venv/bin/python -u agent.py <action> [args].
#
# CLI convention (matches publisher_skill):
#   python -u agent.py <action_id> --flag value --dry-run
#
# Logging: write to stdout (Chief captures and persists in jobs.stdout).

import argparse
import json
import os
import sys


def cmd_hello(args):
    print(json.dumps({"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}))


def cmd_run(args):
    print(f"Running with: {vars(args)}")
    # TODO: implement
    return 0


def main():
    p = argparse.ArgumentParser(description="{{AGENT_DISPLAY_NAME}}")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="action", required=True)

    s_hello = sub.add_parser("hello", help="ping agent")
    s_hello.set_defaults(func=cmd_hello)

    s_run = sub.add_parser("run", help="run main action")
    s_run.add_argument("--input", required=True)
    s_run.set_defaults(func=cmd_run)

    args = p.parse_args()
    rc = args.func(args) or 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
`;

const HTTP_TEMPLATE = `# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (HTTP transport).
# Run as FastAPI server; Chief POSTs to /actions/<id>.

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="{{AGENT_ID}}")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}


@app.post("/actions/{action_id}")
def run_action(action_id: str, body: dict):
    # TODO: dispatch by action_id
    return {"status": "received", "action": action_id, "body": body}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
`;

const REMOTE_TEMPLATE = `# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (remote transport, Kednet via WebSocket).
# Chief отправляет команду Kednet-агенту, Kednet-агент spawn'ит python -u agent.py.

import argparse
import json
import sys


def cmd_hello(args):
    print(json.dumps({"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}))


def cmd_run(args):
    print(f"Running with: {vars(args)}")
    # TODO: implement
    return 0


def main():
    p = argparse.ArgumentParser(description="{{AGENT_DISPLAY_NAME}}")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="action", required=True)

    s_hello = sub.add_parser("hello")
    s_hello.set_defaults(func=cmd_hello)

    s_run = sub.add_parser("run")
    s_run.add_argument("--input", required=True)
    s_run.set_defaults(func=cmd_run)

    args = p.parse_args()
    rc = args.func(args) or 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
`;

const REQUIREMENTS = `# {{AGENT_ID}} — Python deps
# pip install -r requirements.txt (in .venv)
{{DEPS}}
`;

const README = `# {{AGENT_ID}}

Chief-managed agent ({{AGENT_DISPLAY_NAME}}).

## Local run

\`\`\`bash
.venv\\Scripts\\activate  # Windows
python -u agent.py hello
python -u agent.py run --input "test" --dry-run
\`\`\`

## Chief connection

- Registered in Chief's registry (\`/api/agents\`).
- Kednet-агент запускает этот скрипт по команде Chief через WebSocket.
- Артефакты (картинки/аудио) появятся в TG @ChiefAgentbot для approve.
`;

/**
 * Создать скелет агента на Kednet. Вызывает Kednet-агента через WS.
 * @param {object} opts
 * @param {string} opts.agentId
 * @param {string} opts.cwd           — C:\Users\kfigh\<skill>
 * @param {string} opts.templateType  — 'subprocess' | 'http' | 'remote'
 * @param {string} opts.scriptsEntry  — 'scripts/post_channels.py'
 * @param {string[]} opts.envKeys
 * @returns {Promise<{files, requirements}>}
 */
async function createOnKednet({ agentId, cwd, templateType, scriptsEntry, envKeys = [] }) {
  if (!wsHub.isConnected()) {
    throw new Error('kednet agent not connected');
  }
  if (!TEMPLATES[templateType]) {
    throw new Error(`unknown templateType: ${templateType}`);
  }

  const files = {
    'agent.py': SUBPROCESS_TEMPLATE,
    'requirements.txt': REQUIREMENTS,
    'README.md': README
  };

  // Метаданные для Kednet-агента
  const payload = {
    agentId,
    cwd,
    templateType,
    scriptsEntry,
    envKeys,
    files
  };

  const result = await wsHub.requestScaffold(agentId, cwd, JSON.stringify(payload));
  log.info('scaffold done', { agentId, files: result.files, requirements: result.requirements });
  return result;
}

/**
 * Локальный fallback (если Kednet недоступен, например в тестах) — пишет файлы прямо в cwd.
 */
function createLocal({ agentId, cwd, templateType = 'subprocess', displayName = agentId, scriptsEntry, envKeys = [] }) {
  if (fs.existsSync(cwd)) {
    throw new Error(`cwd already exists: ${cwd}`);
  }
  fs.mkdirSync(cwd, { recursive: true });
  fs.mkdirSync(path.join(cwd, 'scripts'), { recursive: true });

  const tmpl = TEMPLATES[templateType] || TEMPLATES.subprocess;
  const rendered = tmpl
    .replace(/\{\{AGENT_ID\}\}/g, agentId)
    .replace(/\{\{AGENT_DISPLAY_NAME\}\}/g, displayName);

  const agentPath = path.join(cwd, 'agent.py');
  fs.writeFileSync(agentPath, rendered, 'utf8');

  const reqPath = path.join(cwd, 'requirements.txt');
  fs.writeFileSync(reqPath, REQUIREMENTS.replace(/\{\{AGENT_ID\}\}/g, agentId).replace(/\{\{DEPS\}\}/g, '# (no deps)'), 'utf8');

  const readmePath = path.join(cwd, 'README.md');
  fs.writeFileSync(readmePath, README.replace(/\{\{AGENT_ID\}\}/g, agentId).replace(/\{\{AGENT_DISPLAY_NAME\}\}/g, displayName), 'utf8');

  const scriptsDir = path.join(cwd, 'scripts');
  if (scriptsEntry) {
    fs.writeFileSync(path.join(scriptsDir, path.basename(scriptsEntry)),
      `# Entry point for ${agentId}\n# Run via Kednet-агент: python -u ${scriptsEntry} <action> [args]\n`,
      'utf8');
  }

  return {
    files: ['agent.py', 'requirements.txt', 'README.md', scriptsEntry ? `scripts/${path.basename(scriptsEntry)}` : null].filter(Boolean),
    requirements: []
  };
}

module.exports = { createOnKednet, createLocal, TEMPLATES };