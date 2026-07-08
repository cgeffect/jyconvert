const fs = require("fs");
const { spawn } = require("child_process");
const {
  pythonRoot,
  bundledPythonBinary,
  bundledFfmpegBinary,
  pythonCommand,
  assertPythonReady,
} = require("./paths");

const path = require("path");

function spawnEnv(extra = {}) {
  const env = { ...process.env, ...extra };
  const homebrew = ["/opt/homebrew/bin", "/usr/local/bin"].filter((dir) => fs.existsSync(dir));
  if (homebrew.length) {
    env.PATH = `${homebrew.join(":")}:${env.PATH || ""}`;
  }
  const ffmpeg = bundledFfmpegBinary();
  if (ffmpeg) {
    env.JYCONVERT_FFMPEG = ffmpeg;
  }
  return env;
}

function spawnProcess(cmd, args, options = {}) {
  const { env: extraEnv, ...rest } = options;
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      ...rest,
      env: spawnEnv(extraEnv),
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

function importDraft({ draftDir, jianyingName, jianyingDraftsRoot }) {
  const args = [
    "--draft-dir",
    draftDir,
    "--jianying-name",
    jianyingName,
  ];
  if (jianyingDraftsRoot) {
    args.push("--jianying-drafts-root", jianyingDraftsRoot);
  }
  return runCli("import", args);
}

module.exports = { convertDraft, importDraft, runCli };
