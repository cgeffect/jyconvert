const fs = require("fs");
const { spawn } = require("child_process");
const {
  pythonRoot,
  bundledPythonBinary,
  pythonCommand,
  assertPythonReady,
} = require("./paths");

const path = require("path");

/** App 内嵌进程默认 PATH 不含 Homebrew，需补上以便找到 ffmpeg */
function spawnEnv() {
  const extra = ["/opt/homebrew/bin", "/usr/local/bin"].filter((dir) => fs.existsSync(dir));
  if (!extra.length) {
    return process.env;
  }
  return { ...process.env, PATH: `${extra.join(":")}:${process.env.PATH || ""}` };
}

function spawnProcess(cmd, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      env: spawnEnv(),
      ...options,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      reject(new Error(`无法启动 ${cmd}: ${err.message}`));
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(stderr.trim() || stdout.trim() || `退出码 ${code}`));
      }
    });
  });
}

function runCli(subcommand, args) {
  assertPythonReady();

  const binary = bundledPythonBinary();
  if (binary) {
    return spawnProcess(binary, [subcommand, ...args]);
  }

  const root = pythonRoot();
  const cliPath = path.join(root, "cli.py");
  return spawnProcess(pythonCommand(), [cliPath, subcommand, ...args], {
    cwd: root,
  });
}

function convertDraft({ protocolPath, resourceRoot, draftName, outputDir }) {
  return runCli("convert", [
    "--protocol",
    protocolPath,
    "--resource-root",
    resourceRoot,
    "--name",
    draftName,
    "--output-dir",
    outputDir,
  ]);
}

function importDraft({ draftDir, jianyingName }) {
  return runCli("import", [
    "--draft-dir",
    draftDir,
    "--jianying-name",
    jianyingName,
  ]);
}

module.exports = { convertDraft, importDraft, runCli };
