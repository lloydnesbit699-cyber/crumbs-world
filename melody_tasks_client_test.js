const fs = require("fs");
const html = fs.readFileSync(__dirname + "/editor.html", "utf8");
const agent = fs.readFileSync(__dirname + "/melody_agent.py", "utf8");

const checks = [
  ["workshop includes a persistent task list", /id="melody-tasks"/.test(html)],
  ["task type and title can be entered", /id="melody-task-kind"/.test(html) && /id="melody-task-title"/.test(html)],
  ["task notes can be entered", /id="melody-task-details"/.test(html)],
  ["tasks load from the authenticated task API", /api\("\/api\/melody\/tasks"\)/.test(html)],
  ["new tasks are saved through the task API", /action: "create", title/.test(html)],
  ["task status changes are saved through the task API", /action: "status", task_id/.test(html)],
  ["task text is escaped before rendering", /esc\(t\.title \|\| "Untitled task"\)/.test(html)],
  ["owner can ask Melody to diagnose the server", /When the owner asks you to troubleshoot the server, use diagnose_system/.test(agent)],
];

let failed = 0;
for (const [label, ok] of checks) {
  console.log(`  ${ok ? "ok" : "FAIL"}: ${label}`);
  if (!ok) failed++;
}
console.log(`\n${checks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
