const { Octokit } = require("@octokit/action");

const octokit = new Octokit();

const [owner, repo] = process.env.GITHUB_REPOSITORY.split("/");
const environmentName = process.env.ENVIRONMENT_NAME;

const { data } = await octokit.request(`DELETE /repos/${owner}/${repo}/environments/${environmentName}`);
console.log("Removed environment", data);
